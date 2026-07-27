"""
scripts/sync_r2.py — Upload Parquet files to Cloudflare R2

同步 Pipeline Parquet 导出到 R2 对象存储，供 DuckDB WASM 浏览器查询。

用法:
  # 设置凭证
  export CF_ACCOUNT_ID="your-account-id"
  export CLOUDFLARE_API_TOKEN="your-token"

  # 同步 (自动检测新文件)
  uv run python scripts/sync_r2.py

  # 强制全量同步
  uv run python scripts/sync_r2.py --force

  # 指定 bucket
  uv run python scripts/sync_r2.py --bucket my-bucket
"""

import argparse
import hashlib
import json
import logging
import mimetypes
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sync_r2")

# ── R2 API helpers ────────────────────────────────────────────────────
R2_API = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}/r2/buckets/{bucket}/objects/{key}"
)


def _headers():
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not token:
        logger.error("CLOUDFLARE_API_TOKEN 未设置")
        sys.exit(1)
    return {"Authorization": f"Bearer {token}"}


def _head_object(account_id: str, bucket: str, key: str) -> dict | None:
    """Check if object exists via HEAD"""
    import httpx

    r = httpx.head(
        R2_API.format(account_id=account_id, bucket=bucket, key=key),
        headers=_headers(),
        timeout=10,
    )
    if r.status_code == 200:
        return {"size": int(r.headers.get("Content-Length", 0)), "etag": r.headers.get("ETag", "")}
    return None


def _upload_object(
    account_id: str,
    bucket: str,
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> bool:
    """PUT object to R2"""
    import httpx

    r = httpx.put(
        R2_API.format(account_id=account_id, bucket=bucket, key=key),
        headers={**_headers(), "Content-Type": content_type},
        content=data,
        timeout=60,
    )
    return r.status_code == 200


def _delete_object(account_id: str, bucket: str, key: str) -> bool:
    """DELETE object from R2"""
    import httpx

    r = httpx.delete(
        R2_API.format(account_id=account_id, bucket=bucket, key=key),
        headers=_headers(),
        timeout=10,
    )
    return r.status_code in (200, 204)


# ── Sync logic ────────────────────────────────────────────────────────


def md5_file(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def local_parquet_files(parquet_dir: str | Path) -> list[Path]:
    """Find all local parquet files in the Hive-partitioned export dir"""
    base = Path(parquet_dir)
    if not base.exists():
        logger.warning(f"Parquet 目录不存在: {base}")
        return []
    return sorted(base.rglob("*.parquet"))


def sync_parquet(
    account_id: str,
    bucket: str,
    local_dir: str | Path,
    prefix: str = "parquet",
    force: bool = False,
) -> dict:
    """
    Sync local Parquet files to R2.

    Strategy:
      - Each file uploaded as parquet/<relative_path>
      - Only upload if md5 differs from remote (skip if same)
      - Generate manifest.json at root
    """
    import httpx

    files = local_parquet_files(local_dir)
    if not files:
        return {"uploaded": 0, "skipped": 0, "deleted": 0, "files": 0}

    logger.info(f"发现 {len(files)} 个本地 Parquet 文件")

    stats = {"uploaded": 0, "skipped": 0, "deleted": 0, "files": len(files)}

    for fpath in files:
        fpath.relative_to(Path(local_dir).parent if prefix else local_dir)
        # key: parquet/year=2026/month=7/date=2026-07-27/data_0.parquet
        key = f"{prefix}/{fpath.relative_to(local_dir).as_posix()}"
        data = fpath.read_bytes()
        local_md5 = md5_file(fpath)

        # Check remote
        remote = _head_object(account_id, bucket, key)

        if remote and remote.get("etag", "").strip('"') == local_md5 and not force:
            stats["skipped"] += 1
            continue

        # Upload
        content_type = "application/octet-stream"
        ct_guess, _ = mimetypes.guess_type(fpath.name)
        if ct_guess:
            content_type = ct_guess

        ok = _upload_object(account_id, bucket, key, data, content_type)
        if ok:
            stats["uploaded"] += 1
            logger.info(f"  ↑ {key} ({len(data) / 1024:.0f} KB)")
        else:
            logger.error(f"  ✗ {key} 上传失败")

    # Generate manifest
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket,
        "prefix": prefix,
        "files": [],
    }
    # List remote objects
    try:
        import httpx

        list_url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
            f"/r2/buckets/{bucket}/objects?prefix={prefix}"
        )
        r = httpx.get(list_url, headers=_headers(), timeout=15)
        if r.status_code == 200:
            data = r.json()
            objs = data.get("result", {}).get("objects", data.get("result", []))
            if isinstance(objs, list):
                for obj in objs:
                    manifest["files"].append(
                        {
                            "key": obj.get("key", obj.get("name", "")),
                            "size": obj.get("size", 0),
                            "etag": obj.get("etag", "").strip('"'),
                        }
                    )
    except Exception as e:
        logger.warning(f"Manifest 生成失败: {e}")

    # Upload manifest
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    _upload_object(account_id, bucket, "manifest.json", manifest_bytes, "application/json")
    logger.info(f"  ↑ manifest.json ({len(manifest_bytes)} B)")

    return stats


# ── CLI ───────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Sync Parquet files to Cloudflare R2")
    parser.add_argument("--bucket", default="pulse-data-engine-parquet", help="R2 bucket name")
    parser.add_argument(
        "--parquet-dir", default="data/ods_parquet", help="Local Parquet export directory"
    )
    parser.add_argument("--prefix", default="parquet", help="R2 object key prefix")
    parser.add_argument("--force", action="store_true", help="Force re-upload all files")
    args = parser.parse_args()

    account_id = os.environ.get("CF_ACCOUNT_ID", "")
    if not account_id:
        logger.error("CF_ACCOUNT_ID 环境变量未设置")
        sys.exit(1)

    stats = sync_parquet(
        account_id=account_id,
        bucket=args.bucket,
        local_dir=args.parquet_dir,
        prefix=args.prefix,
        force=args.force,
    )

    logger.info(
        f"同步完成: {stats['uploaded']} 上传, {stats['skipped']} 跳过, 共 {stats['files']} 文件"
    )


if __name__ == "__main__":
    main()
