#!/usr/bin/env python3
"""
scripts/ingest_playlist.py — 播放列表/频道批量吞噬 wrapper

在 ingest_produce.py 外层: 列出 playlist/channel 全部视频 → 跳过已处理
(video_id 去重, 扫 data/ingest/*.json + data/scene2_intel/*.json) → 逐个吞噬。

用法:
  uv run python -m scripts.ingest_playlist "https://www.youtube.com/playlist?list=XXX"
  uv run python -m scripts.ingest_playlist "https://www.youtube.com/@channel/videos" --dry-run
  uv run python -m scripts.ingest_playlist URL --limit 5 --score 70 --lang auto
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
INGEST = PROJECT / "data" / "ingest"
SCENE2 = PROJECT / "data" / "scene2_intel"

YTDLP_BASE = [
    "yt-dlp",
    "--cookies-from-browser",
    "brave",
    "--extractor-args",
    "youtube:player-client=ios,android_embedded,web",
]


def list_videos(url: str) -> list[dict]:
    """flat 列表: id|title|duration, 不下载任何内容"""
    r = subprocess.run(
        YTDLP_BASE + ["--flat-playlist", "--print", "%(id)s|%(title)s|%(duration)s", url],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        print(f"[playlist] 列出失败: {r.stderr[-300:]}")
        return []
    videos = []
    for line in r.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) >= 2 and parts[0].strip():
            videos.append(
                {
                    "id": parts[0].strip(),
                    "title": parts[1].strip(),
                    "duration": parts[2].strip() if len(parts) > 2 else "",
                }
            )
    return videos


def load_seen_ids() -> set[str]:
    """已处理 video_id: data/ingest/*.json + data/scene2_intel/*.json"""
    seen: set[str] = set()
    for d in (INGEST, SCENE2):
        if not d.exists():
            continue
        for jf in d.glob("*.json"):
            try:
                meta = json.loads(jf.read_text(encoding="utf-8"))
                if meta.get("video_id"):
                    seen.add(meta["video_id"])
            except (json.JSONDecodeError, OSError):
                continue
    return seen


def _lcs_len(a: str, b: str) -> int:
    """最长公共子串长度 (中文相关性子串匹配)"""
    if not a or not b:
        return 0
    m, n = len(a), len(b)
    dp = [0] * (n + 1)
    best = 0
    for i in range(1, m + 1):
        prev = 0
        for j in range(1, n + 1):
            tmp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev + 1
                best = max(best, dp[j])
            else:
                dp[j] = 0
            prev = tmp
    return best


def _title_relevant(title: str, topic: str, min_cn=4, min_latin=3) -> bool:
    """候选标题与选题相关性预检 (C3 门禁, 2026-09-04)

    中文: 标题与选题最长公共子串 ≥4 字 (去空白后)。
    拉丁词: topic 中的拉丁词 (AI/RAG/GDPR...) 标题须含至少一个 (≥3 字符)。
    例: topic "ai出海合规评估时机与流程" + SocialEcho 英文推广标题 → 0 匹配 → 拒。
    """
    t_norm = re.sub(r"\s+", "", title.lower())
    q_norm = re.sub(r"\s+", "", topic.lower())
    cn_ok = _lcs_len(t_norm, q_norm) >= min_cn
    latin_words = re.findall(r"[a-z][a-z0-9\-]{2,}", q_norm)
    latin_ok = (not latin_words) or any(w in t_norm for w in latin_words)
    return cn_ok and latin_ok


def _latest_ingest_md(after_ts: float, limit_sec: int = 120) -> Path | None:
    """吞噬后找新产物 md (data/ingest/ 最近写入)"""
    candidates = []
    for d in (INGEST, SCENE2):
        if d.exists():
            candidates.extend(d.glob("*.md"))
    fresh = [p for p in candidates if p.stat().st_mtime > after_ts]
    if not fresh:
        return None
    return max(fresh, key=lambda p: p.stat().st_mtime)


def consume_queue(args) -> int:
    """消费选题队列: approved 且未 done → 逐个 ingest_produce → 标记 done"""
    queue_dir = PROJECT / "data" / "ingest" / "queue"
    if not queue_dir.exists():
        print("[queue] 队列目录不存在")
        return 0
    items = []
    for f in sorted(queue_dir.glob("*.json")):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if m.get("status") == "approved" and not m.get("done_at"):
            items.append((f, m))
    if not items:
        print("[queue] 无已批准待消费选题")
        return 0
    # 按优先级 + 价值排序
    items.sort(key=lambda x: (x[1].get("priority", 9), -x[1].get("expected_value", 0)))
    print(f"[queue] 待消费 {len(items)} 个选题")

    for f, m in items:
        topic = m["topic"]
        urls = m.get("candidates_urls") or []
        if not urls:
            # 无 URL: ytsearch 抓 3 个候选 (仅当 --ytsearch 开启)
            if not getattr(args, "ytsearch", False):
                print(f"  跳过 {topic}: 无 candidates_urls (人工填 URL 或加 --ytsearch)")
                continue
            r = subprocess.run(
                YTDLP_BASE
                + ["--flat-playlist", "--print", "%(id)s|%(title)s", f"ytsearch3:{topic}"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            cands = [
                (ln.split("|")[0].strip(), ln.split("|", 1)[1].strip() if "|" in ln else "")
                for ln in r.stdout.splitlines()
                if "|" in ln
            ]
            # C3 门禁: 标题相关性预检 — 全不相关 → 记 skipped, 不吞噬不置 done
            relevant = [(vid, t) for vid, t in cands if _title_relevant(t, topic)]
            if not relevant:
                m["skipped_at"] = datetime.now(timezone.utc).isoformat()
                m["skipped_reason"] = (
                    f"ytsearch 候选标题与选题不相关 (共 {len(cands)} 个): "
                    + "; ".join(t[:40] for _, t in cands[:3])
                )
                f.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  ✗ {topic}: 候选全不相关, 跳过 (已记 skipped)")
                continue
            if len(relevant) < len(cands):
                print(f"  [C3] {topic}: 过滤 {len(cands) - len(relevant)} 个不相关候选")
            urls = [f"https://youtu.be/{vid}" for vid, _ in relevant]
        if not urls:
            print(f"  跳过 {topic}: 未找到候选 URL")
            continue
        url = urls[0]
        print(f"\n[{topic}] 吞噬: {url}")
        before_ts = time.time()
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.ingest_produce",
                url,
                "--lang",
                args.lang,
                "--score",
                str(args.score),
                "--domain",
                "course",
            ],
            cwd=str(PROJECT),
            timeout=3600,
        )
        if r.returncode == 0:
            # C3 门禁: 产物长度下限 (转录提炼后 md 应 ≥1500 字符; 过短 = 内容无实质)
            prod = _latest_ingest_md(before_ts)
            if prod is None or prod.stat().st_size < 1500:
                m["skipped_at"] = datetime.now(timezone.utc).isoformat()
                m["skipped_reason"] = (
                    f"产物过短: {prod.name if prod else '未找到'} "
                    f"({prod.stat().st_size if prod else 0} 字节 < 1500), 内容无实质, 不置 done"
                )
                f.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  ✗ {topic}: 产物过短, 不置 done (已记 skipped)")
                continue
            m["done_at"] = datetime.now(timezone.utc).isoformat()
            m["consumed_url"] = url
            f.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ✓ {topic} 完成 (产物 {prod.stat().st_size} 字节)")
        else:
            print(f"  ⚠ {topic} 吞噬失败, 保留队列")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="播放列表/频道批量吞噬 (video_id 去重)")
    ap.add_argument("url", help="playlist/channel/单视频 URL")
    ap.add_argument("--dry-run", action="store_true", help="只列待处理, 不执行")
    ap.add_argument("--limit", type=int, default=0, help="最多处理 N 个 (0=全部)")
    ap.add_argument("--score", type=int, default=60, help="自评分传给 ingest_produce")
    ap.add_argument("--lang", default="auto", help="whisper 语言 (auto/en/zh...)")
    ap.add_argument(
        "--queue",
        action="store_true",
        help="消费选题队列: data/ingest/queue/ 中 approved 且未 done 的选题",
    )
    ap.add_argument(
        "--ytsearch", action="store_true", help="队列消费时对无 URL 选题自动 ytsearch3 抓候选"
    )
    args = ap.parse_args()

    if args.queue:
        return consume_queue(args)
    videos = list_videos(args.url)
    if not videos:
        print("[playlist] 未取到视频列表")
        return 1
    print(f"[playlist] 共 {len(videos)} 个视频")

    seen = load_seen_ids()
    pending = [v for v in videos if v["id"] not in seen]
    print(f"[playlist] 已处理 {len(videos) - len(pending)}, 待处理 {len(pending)}")
    if not pending:
        print("[playlist] 全部已处理, 无需吞噬")
        return 0

    if args.limit:
        pending = pending[: args.limit]

    for i, v in enumerate(pending, 1):
        dur = v["duration"]
        print(f"\n[{i}/{len(pending)}] {v['id']} | {v['title'][:60]} | {dur}s")
        if args.dry_run:
            continue
        # 时长过滤: 超过 2h 或短于 3min 的跳过 (素材价值/成本)
        try:
            if dur and (int(dur) > 7200 or int(dur) < 180):
                print(f"  跳过: 时长 {dur}s 不在 3min-2h 区间")
                continue
        except ValueError:
            pass
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.ingest_produce",
                f"https://youtu.be/{v['id']}",
                "--lang",
                args.lang,
                "--score",
                str(args.score),
            ],
            cwd=str(PROJECT),
            timeout=3600,
        )
        if r.returncode != 0:
            print(f"  ⚠ 失败: {v['id']} (exit={r.returncode}), 继续下一个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
