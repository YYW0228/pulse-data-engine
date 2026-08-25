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
import subprocess
import sys
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


def main() -> int:
    ap = argparse.ArgumentParser(description="播放列表/频道批量吞噬 (video_id 去重)")
    ap.add_argument("url", help="playlist/channel/单视频 URL")
    ap.add_argument("--dry-run", action="store_true", help="只列待处理, 不执行")
    ap.add_argument("--limit", type=int, default=0, help="最多处理 N 个 (0=全部)")
    ap.add_argument("--score", type=int, default=60, help="自评分传给 ingest_produce")
    ap.add_argument("--lang", default="auto", help="whisper 语言 (auto/en/zh...)")
    args = ap.parse_args()

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
