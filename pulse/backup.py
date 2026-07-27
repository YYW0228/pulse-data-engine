"""
pulse/backup.py — DuckDB 备份策略

备份链:
  Local: DuckDB → gzip → data/backups/jobs_{timestamp}.duckdb.gz
  Remote: gzip → Cloudflare R2 → backups/pulse/jobs_{timestamp}.duckdb.gz
  Restore: 从 R2 下载 → gunzip → 还原
"""

import gzip
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("pulse.backup")


class BackupManager:
    def __init__(
        self,
        db_path: str = "data/jobs.duckdb",
        backup_dir: str = "data/backups",
        r2_bucket: str | None = None,
    ):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.r2_bucket = r2_bucket

    def backup_local(self) -> Path:
        """本地 gzip 压缩备份"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"jobs_{timestamp}.duckdb.gz"

        t0 = time.time()
        db_size = self.db_path.stat().st_size
        with (
            open(self.db_path, "rb") as f_in,
            gzip.open(backup_file, "wb", compresslevel=6) as f_out,
        ):
            shutil.copyfileobj(f_in, f_out)

        compressed = backup_file.stat().st_size
        ratio = compressed / db_size * 100 if db_size else 0
        elapsed = time.time() - t0
        logger.info(
            f"本地备份: {backup_file.name} ({db_size / 1024:.0f}KB → {compressed / 1024:.0f}KB, "
            f"{ratio:.0f}%, {elapsed:.1f}s)"
        )
        return backup_file

    def backup_remote(self, backup_file: Path | None = None) -> str | None:
        """备份到 Cloudflare R2"""
        if not self.r2_bucket:
            logger.warning("R2 bucket 未配置, 跳过远程备份")
            return None

        backup_file = backup_file or self.backup_local()

        try:
            import httpx

            token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
            account_id = os.environ.get("CF_ACCOUNT_ID", "")
            if not token or not account_id:
                logger.warning("CLOUDFLARE_API_TOKEN 或 CF_ACCOUNT_ID 未设置, 跳过 R2 备份")
                return None

            # 通过 Worker 上传到 R2 (用 put_object API)
            object_key = f"backups/pulse/{backup_file.name}"

            data = backup_file.read_bytes()
            r = httpx.put(
                f"https://api.cloudflare.com/client/v4/accounts/"
                f"{account_id}/r2/buckets/"
                f"{self.r2_bucket}/objects/{object_key}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/octet-stream",
                },
                content=data,
                timeout=30,
            )
            if r.status_code == 200:
                logger.info(f"R2 备份: {object_key} ({len(data) / 1024:.0f}KB)")
                return object_key
            else:
                logger.warning(f"R2 上传失败: HTTP {r.status_code}")
                return None
        except Exception as e:
            logger.error(f"R2 备份异常: {e}")
            return None

    def restore(self, source: str, target_db: str | None = None) -> Path:
        """从备份文件恢复

        Args:
            source: 本地路径或 r2:// 前缀的远程路径
            target_db: 目标 DB 路径, 默认覆盖当前 DB
        """
        target = Path(target_db or self.db_path)

        if source.startswith("r2://"):
            return self._restore_from_r2(source[5:], target)
        else:
            return self._restore_from_local(Path(source), target)

    def _restore_from_local(self, source: Path, target: Path) -> Path:
        t0 = time.time()
        with gzip.open(source, "rb") as f_in, open(target, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        logger.info(f"本地恢复: {source.name} → {target} ({time.time() - t0:.1f}s)")
        return target

    def _restore_from_r2(self, object_key: str, target: Path) -> Path:
        import httpx

        token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
        r = httpx.get(
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{os.environ.get('CF_ACCOUNT_ID', '')}/r2/buckets/"
            f"{self.r2_bucket}/objects/{object_key}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        r.raise_for_status()
        local_gz = self.backup_dir / Path(object_key).name
        local_gz.write_bytes(r.content)
        return self._restore_from_local(local_gz, target)

    def list_backups(self) -> list[dict]:
        """列出所有可用备份"""
        backups = []
        for f in sorted(self.backup_dir.glob("*.duckdb.gz"), reverse=True):
            backups.append(
                {
                    "file": f.name,
                    "size_kb": f.stat().st_size / 1024,
                    "modified": datetime.fromtimestamp(
                        f.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )
        return backups

    def cleanup(self, keep_last: int = 7) -> None:
        """清理旧备份 (保留最近 N 个)"""
        backups = sorted(self.backup_dir.glob("*.duckdb.gz"), reverse=True)
        for f in backups[keep_last:]:
            f.unlink()
            logger.info(f"清理旧备份: {f.name}")
