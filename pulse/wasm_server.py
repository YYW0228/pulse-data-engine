"""
pulse/wasm_server.py — 本地 Parquet HTTP 服务器

模拟 Cloudflare Worker 的 CORS + Range 行为，供 DuckDB WASM 在浏览器中
通过 read_parquet() 直接查询 Parquet 文件。

用法:
  uv run python -m pulse.wasm_server       # 默认 8000 端口
  uv run python -m pulse.wasm_server --port 8080 --parquet-dir data/ods_parquet

架构:
  wasm_query.html (浏览器)
        ↕ SQL via DuckDB WASM
  read_parquet('http://localhost:8000/parquet/...')
        ↕ HTTP Range requests (CORS + 206 Partial Content)
  wasm_server.py  ←  filesystem: data/ods_parquet/
"""

import argparse
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

logger = logging.getLogger("pulse.wasm_server")

# ─── CORS + Range-aware HTTP handler ──────────────────────────────────


class ParquetHTTPHandler(SimpleHTTPRequestHandler):
    """HTTP handler that serves Parquet files with CORS and Range support."""

    # Override to inject CORS + Range handling
    parquet_dir: str = "data/ods_parquet"
    server_start: float = 0.0

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(Path(__file__).parent.parent), **kwargs)

    def _send_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        self.send_header(
            "Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length"
        )

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors()
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = self.path

        # ── Health / Pipeline 状态 ──────────────────────────────────
        if parsed == "/" or parsed == "/health":
            # 尝试加载管道状态
            status = "ok"
            pipeline = {}
            db_path = Path(self.parquet_dir).parent / "jobs.duckdb"
            if db_path.exists():
                try:
                    from pulse.dag import DAG

                    dag = DAG(name="pulse_etl", db_path=str(db_path))
                    pipeline = dag.health()
                    dag.close()
                except Exception as e:
                    pipeline = {"error": str(e)}

            self._json_response(
                {
                    "status": status,
                    "service": "pulse-data-engine",
                    "docs": "https://github.com/YYW0228/pulse-data-engine",
                    "pipeline": pipeline,
                    "uptime_s": round(time.time() - self.server_start, 1),
                }
            )
            return

        # ── Manifest ────────────────────────────────────────────
        if parsed == "/manifest.json":
            self._serve_manifest()
            return

        # ── Parquet files (with CORS + Range) ───────────────────
        if parsed.startswith("/parquet/"):
            self._serve_parquet(parsed)
            return

        # ── Static files (wasm_query.html etc) ──────────────────
        if parsed == "/" or parsed == "/wasm":
            self.path = "/pulse/static/wasm_query.html"
        super().do_GET()

    def _json_response(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self._send_cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_manifest(self) -> None:
        """Generate manifest.json from local parquet files"""
        base = Path(self.parquet_dir)
        files = sorted(base.rglob("*.parquet"))
        manifest: dict = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "local",
            "prefix": "parquet",
            "total_size_bytes": sum(f.stat().st_size for f in files),
            "files": [],
        }
        for f in files:
            rel = f.relative_to(base).as_posix()
            manifest["files"].append(
                {
                    "key": f"parquet/{rel}",
                    "size": f.stat().st_size,
                }
            )
        self._json_response(manifest)

    def _serve_parquet(self, path: str) -> None:
        """Serve Parquet file with CORS + Range"""
        # path = "/parquet/year=2026/month=7/..."
        rel = path.lstrip("/")
        file_path = Path(self.parquet_dir) / rel[len("parquet/") :]

        if not file_path.exists() or not file_path.is_file():
            self.send_response(404)
            self._send_cors()
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        file_size = file_path.stat().st_size
        data = file_path.read_bytes()

        # ── Range request ──────────────────────────────────────────
        range_header = self.headers.get("Range", "")
        if range_header:
            match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else file_size - 1
                chunk = data[start : end + 1]

                self.send_response(206)
                self._send_cors()
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(chunk)))
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "public, max-age=3600")
                self.end_headers()
                self.wfile.write(chunk)
                logger.debug(f"Range {path}: bytes {start}-{end}/{file_size}")
                return

        # ── Full response ──────────────────────────────────────────
        self.send_response(200)
        self._send_cors()
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)
        logger.debug(f"Full: {path} ({file_size} B)")

    def log_message(self, format, *args) -> None:
        logger.info(format % args)


def run_server(host: str = "0.0.0.0", port: int = 8000, parquet_dir: str = "data/ods_parquet"):
    """Start the WASM Parquet HTTP server"""
    ParquetHTTPHandler.parquet_dir = parquet_dir
    ParquetHTTPHandler.server_start = time.time()

    os.makedirs(parquet_dir, exist_ok=True)

    server = HTTPServer((host, port), ParquetHTTPHandler)
    logger.info(f"🚀 Pulse WASM Server: http://{host}:{port}")
    logger.info(f"   Parquet 目录: {os.path.abspath(parquet_dir)}")
    logger.info(f"   SQL 查询页面: http://localhost:{port}/wasm")
    logger.info("   Streamlit:    http://localhost:8501")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("服务器停止")
        server.server_close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Pulse WASM Local Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--parquet-dir", default="data/ods_parquet")
    args = parser.parse_args()
    run_server(args.host, args.port, args.parquet_dir)
