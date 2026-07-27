"""
pulse/metrics_server.py — Prometheus /metrics HTTP 端点

提供 Prometheus scrape target 供 Grafana/Prometheus 采集。

用法:
  uv run python -m pulse.metrics_server       # 默认 9464 端口
  uv run python -m pulse.metrics_server --port 9464

集成: Makefile 中有 make serve-metrics 目标
"""

import argparse
import logging
from wsgiref.simple_server import WSGIRequestHandler, make_server

from prometheus_client import make_wsgi_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pulse.metrics")


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {args[0]} {args[1]}")


def run(host: str = "0.0.0.0", port: int = 9464) -> None:
    # 确保 pulse.metrics 被初始化 (注册所有自定义指标)
    import pulse.metrics  # noqa: F401

    # 包装 WSGI app 以支持 /snapshot 端点
    from pulse.metrics import SNAPSHOT_PATH

    metrics_app = make_wsgi_app()

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "")

        # 提供最新运行快照
        if path == "/snapshot":
            if SNAPSHOT_PATH.exists():
                data = SNAPSHOT_PATH.read_text()
                start_response(
                    "200 OK",
                    [("Content-Type", "application/json"), ("Access-Control-Allow-Origin", "*")],
                )
                return [data.encode()]
            start_response("200 OK", [("Content-Type", "application/json")])
            return [b"{}"]

        # 健康检查
        if path == "/health":
            import json

            status = {"service": "pulse-metrics", "status": "ok"}
            if SNAPSHOT_PATH.exists():
                import json as j

                status["last_run"] = j.loads(SNAPSHOT_PATH.read_text()).get("timestamp", "?")
            data = json.dumps(status).encode()
            start_response("200 OK", [("Content-Type", "application/json")])
            return [data]

        return metrics_app(environ, start_response)

    httpd = make_server(host, port, app, handler_class=QuietHandler)
    logger.info(f"📊 Pulse Metrics: http://{host}:{port}/metrics")
    logger.info(f"   Last-run snapshot: http://{host}:{port}/snapshot")
    logger.info(f"   Prometheus scrape target: {host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Metrics server stopped")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9464)
    args = parser.parse_args()
    run(args.host, args.port)
