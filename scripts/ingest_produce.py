#!/usr/bin/env python3
"""
scripts/ingest_produce.py — Mac mini 素材工厂: YouTube → 中文吞噬素材 → data/ingest/

流程 (全本地, 零云端):
  1. 字幕优先: yt-dlp 拉自动字幕 (en/zh), 有则直接用
  2. 无字幕: yt-dlp 下音频 (brave cookies) → whisper.cpp turbo 转录
  3. 本地 LLM 吞噬: llama-server (Qwen3.5-9B, 127.0.0.1:8080) 分段吞噬 → 6 段结构素材
  4. 产物: {title-slug}.md + metadata.json → data/ingest/
  5. 可选: git add/commit/push (推送到主线私有仓)

依赖: yt-dlp (brave cookies), whisper.cpp ($WHISPER_CPP_DIR), llama-server 已跑
用法:
  uv run python -m scripts.ingest_produce "https://www.youtube.com/watch?v=XXX"
  uv run python -m scripts.ingest_produce URL --no-push --keep-transcript
  uv run python -m scripts.ingest_produce URL --llm-url http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
INGEST = PROJECT / "data" / "ingest"
WHISPER_DIR = Path(os.environ.get("WHISPER_CPP_DIR", str(Path.home() / "whisper.cpp")))
WHISPER_CLI = WHISPER_DIR / "build" / "bin" / "whisper-cli"
TURBO_MODEL = WHISPER_DIR / "models" / "ggml-large-v3-turbo.bin"

YTDLP_BASE = [
    "yt-dlp",
    "--cookies-from-browser",
    "brave",
    "--extractor-args",
    "youtube:player-client=ios,android_embedded,web",
]

SYSTEM_PROMPT = (
    "你是课程素材编辑, 负责把英文视频转录整理成中文培训素材。"
    "要求: 忠实于转录内容, 不编造转录中没有的事实; 术语准确; 中文输出。"
)


def run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        print(f"[ingest] 命令失败: {' '.join(cmd[:3])}...\n{r.stderr[-500:]}")
    return r


def fetch_meta(url: str) -> dict:
    r = run(
        ytdlp_cmd(
            [
                "--print",
                "%(title)s",
                "--print",
                "%(channel)s",
                "--print",
                "%(duration_string)s",
                "--print",
                "%(webpage_url)s",
                "--print",
                "%(id)s",
            ],
            url,
        )
    )
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    return {
        "title": lines[0] if lines else url,
        "channel": lines[1] if len(lines) > 1 else "",
        "duration": lines[2] if len(lines) > 2 else "",
        "url": lines[3] if len(lines) > 3 else url,
        "video_id": lines[4] if len(lines) > 4 else "",
    }


def ytdlp_cmd(args: list[str], url: str) -> list[str]:
    return YTDLP_BASE + args + [url]


def get_transcript(url: str, workdir: Path) -> Path | None:
    """字幕优先, 无字幕返回 None"""
    r = run(
        ytdlp_cmd(
            [
                "--skip-download",
                "--write-auto-subs",
                "--sub-langs",
                "en,zh-Hans,zh",
                "--sub-format",
                "vtt",
                "--convert-subs",
                "vtt",
                "-o",
                f"{workdir}/%(title)s.%(ext)s",
            ],
            url,
        )
    )
    if r.returncode != 0:
        return None
    vtts = sorted(workdir.glob("*.vtt"))
    if not vtts:
        return None
    sub = vtts[0]
    out = workdir / "transcript_from_sub.txt"
    text = []
    for line in sub.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("WEBVTT") or "-->" in line or not line.strip():
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line:
            text.append(line)
    out.write_text("\n".join(text), encoding="utf-8")
    return out


def whisper_transcribe(url: str, workdir: Path, lang: str = "auto") -> Path | None:
    """whisper.cpp turbo 转录, 返回 txt 路径 (lang=auto 时自动检测语言)"""
    audio_dir = workdir / "audio"
    audio_dir.mkdir(exist_ok=True)
    r = run(
        ytdlp_cmd(
            [
                "-f",
                "bestaudio",
                "--extract-audio",
                "--audio-format",
                "wav",
                "--postprocessor-args",
                "ffmpeg:-ar 16000 -ac 1",
                "-o",
                f"{audio_dir}/%(title)s.%(ext)s",
            ],
            url,
        )
    )
    if r.returncode != 0:
        return None
    wavs = (
        sorted(audio_dir.glob("*.wav"))
        + sorted(audio_dir.glob("*.mp3"))
        + sorted(audio_dir.glob("*.m4a"))
    )
    if not wavs:
        return None
    audio = wavs[0]
    out_prefix = workdir / "transcript"
    cli = [
        str(WHISPER_CLI),
        "-m",
        str(TURBO_MODEL),
        "-f",
        str(audio),
        "-t",
        "8",
        "-otxt",
        "-of",
        str(out_prefix),
        "-np",
    ]
    if lang and lang != "auto":
        cli += ["-l", lang]  # auto = 不传 -l, whisper.cpp 自动检测语言
    r = run(cli, timeout=1800)
    txt = workdir / "transcript.txt"
    if txt.exists() and txt.stat().st_size > 100:
        return txt
    # whisper.cpp 输出格式: {prefix}.txt
    for p in workdir.glob("transcript*.txt"):
        if p.stat().st_size > 100:
            return p
    return None


def llm_chat(prompt: str, llm_url: str, max_tokens: int = 1600, system: str | None = None) -> str:
    import urllib.request

    body = json.dumps(
        {
            "model": "local",
            "messages": [
                {"role": "system", "content": system or SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "chat_template_kwargs": {
                "enable_thinking": False
            },  # Qwen3 必须关 thinking, 否则 content 为空
        }
    ).encode()
    req = urllib.request.Request(
        llm_url.rstrip("/") + "/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def digest(transcript: Path, meta: dict, llm_url: str) -> str:
    """本地 LLM 分段吞噬 → 6 段结构素材"""
    full = transcript.read_text(encoding="utf-8")
    mid = len(full) // 2
    print(f"[ingest] 转录 {len(full)} 字符, 分段吞噬...", flush=True)
    s1 = llm_chat(
        "以下是英文视频转录前半段。请输出:\n1) 章节要点(3-6条, 按主题分, 标注大致时间区间)\n2) 关键概念(术语+一句话中文解释)\n转录:\n"
        + full[:mid],
        llm_url,
    )
    s2 = llm_chat(
        "以下是英文视频转录后半段。请输出:\n1) 章节要点(3-6条, 按主题分, 标注大致时间区间)\n2) 关键概念(术语+一句话中文解释)\n转录:\n"
        + full[mid:],
        llm_url,
    )
    print("[ingest] 汇总 6 段结构...", flush=True)
    return llm_chat(
        "基于以下两段素材摘要, 按模板生成6段结构的中文课程素材:\n"
        "一、核心论点 (TL;DR)\n二、章节摘要 (含时间戳)\n三、关键概念卡片\n"
        "四、金句 (可作课程引用, 中英对照)\n五、与主线课程/本司架构的映射\n六、参考练习题\n\n"
        f"信源信息: 标题 '{meta['title']}', 作者 {meta['channel']}, 时长 {meta['duration']}, "
        f"URL {meta['url']}, 吞噬日期 {datetime.now(timezone.utc).date().isoformat()}。\n"
        "第五段可提及: 本司 RAG 架构用 DuckDB VSS + bge-small-zh 向量检索 + DeepSeek 生成, "
        "有引用验证门禁与 llm_audit 审计不变量; 不得虚构其他系统细节。\n\n"
        f"=== 前半段摘要 ===\n{s1}\n\n=== 后半段摘要 ===\n{s2}\n\n生成完整6段结构素材:",
        max_tokens=2500,
        system=SYSTEM_PROMPT + "你是主线业务课程素材主编。",
        llm_url=llm_url,
    )


def slugify(title: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title).strip("-").lower()
    return (s or "untitled")[:60]


def main() -> int:
    ap = argparse.ArgumentParser(description="Mac mini 素材工厂: YouTube → 中文吞噬素材")
    ap.add_argument("url")
    ap.add_argument("--llm-url", default=os.environ.get("LLAMA_URL", "http://127.0.0.1:8080"))
    ap.add_argument("--no-push", action="store_true", help="不 git push (测试模式)")
    ap.add_argument("--keep-transcript", action="store_true", help="保留转录原文")
    ap.add_argument("--score", type=int, default=60, help="自评分 0-100")
    ap.add_argument("--lang", default="auto", help="whisper 语言: auto(默认自动检测)/en/zh/ja...")
    ap.add_argument(
        "--domain",
        default="course",
        choices=["course", "compliance", "sales", "internal-ops"],
        help="素材域 (可扩展枚举): course=课程素材(默认)/compliance=合规/sales=销售/internal-ops",
    )
    args = ap.parse_args()

    if not WHISPER_CLI.exists() or not TURBO_MODEL.exists():
        print(
            f"[ingest] 缺 whisper.cpp 组件: cli={WHISPER_CLI.exists()} model={TURBO_MODEL.exists()}"
        )
        return 1

    INGEST.mkdir(parents=True, exist_ok=True)
    workdir = Path(f"/tmp/ingest_produce_{int(time.time())}")
    workdir.mkdir(parents=True, exist_ok=True)

    meta = fetch_meta(args.url)
    print(f"[ingest] {meta['title']} | {meta['channel']} | {meta['duration']}")

    transcript = get_transcript(args.url, workdir)
    source = "subtitle" if transcript else None
    if not transcript:
        print("[ingest] 无字幕, whisper.cpp 转录...")
        transcript = whisper_transcribe(args.url, workdir, lang=args.lang)
        source = "whisper.cpp"
    if not transcript:
        print("[ingest] 转录失败")
        return 1
    print(
        f"[ingest] 转录就绪: {transcript.name} ({transcript.stat().st_size} bytes, 来源={source})"
    )

    md_content = digest(transcript, meta, args.llm_url)
    if len(md_content) < 500:
        print(f"[ingest] 吞噬产物异常短 ({len(md_content)}), 疑似失败, 中止")
        return 1

    slug = slugify(meta["title"])
    md_path = INGEST / f"ingest-{slug}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.md"
    md_path.write_text(md_content, encoding="utf-8")

    metadata = {
        "title": meta["title"],
        "channel": meta["channel"],
        "url": meta["url"],
        "video_id": meta.get("video_id", ""),
        "duration": meta["duration"],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "transcript_source": source,
        "self_score": args.score,
        "language": args.lang,
        "ingest_engine": "local-qwen3.5-9b",
        "domain": args.domain,
    }
    meta_path = md_path.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.keep_transcript:
        shutil.copy2(transcript, INGEST / f"{slug}.transcript.txt")

    print(f"[ingest] 产物: {md_path.name} (+metadata.json)")
    if not args.no_push:
        r = run(["git", "-C", str(PROJECT), "add", "data/ingest/"], timeout=60)
        if r.returncode == 0:
            run(
                [
                    "git",
                    "-C",
                    str(PROJECT),
                    "commit",
                    "-m",
                    f"ingest: {meta['title'][:60]} (source={source}, score={args.score})",
                ],
                timeout=60,
            )
            push = run(["git", "-C", str(PROJECT), "push"], timeout=120)
            print("[ingest] push:", "OK" if push.returncode == 0 else "FAILED")
    shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
