#!/bin/bash
# ============================================================
# deploy_client.sh — 客户版一键部署 (解决 HF/GFW + 环境安装两大摩擦)
# 目标: 新 macOS/Linux 机器上 从零到 8502 可访问 ≤15 分钟, 零人工干预
# 用法:  bash deploy_client.sh [--offline /path/to/models] [--port 8502]
#   --offline: 模型从本地路径复制 (断外网可装), 默认走 hf-mirror → huggingface.co 回退
# ============================================================
set -euo pipefail

PORT="${PORT:-8502}"
REPO_URL="https://github.com/YYW0228/pulse-data-engine.git"
APP_DIR="${APP_DIR:-$HOME/pulse-data-engine}"
MODEL_NAME="BAAI/bge-small-zh-v1.5"
OFFLINE_SRC="${OFFLINE_SRC:-}"

echo "=== 客户版一键部署 (pulse 合规问答) ==="
START_TS=$(date +%s)

# ---------- 1. 基础工具 (brew/python/ffmpeg) ----------
if [[ "$(uname)" == "Darwin" ]]; then
  command -v brew >/dev/null || { echo "安装 Homebrew..."; /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; }
  command -v python3.11 >/dev/null || brew install python@3.11
  command -v ffmpeg >/dev/null || brew install ffmpeg
else
  command -v python3.11 >/dev/null || { echo "请先安装 python3.11: apt install python3.11 或使用 pyenv"; exit 1; }
  command -v ffmpeg >/dev/null || sudo apt-get install -y ffmpeg
fi
command -v uv >/dev/null || { echo "安装 uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; }

# ---------- 2. 代码 + 依赖 ----------
if [ ! -d "$APP_DIR/.git" ]; then
  echo "--- clone 产品代码 ---"
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
echo "--- 安装依赖 (uv sync) ---"
uv sync --quiet

# ---------- 3. 模型 (零 GFW 依赖) ----------
MODEL_CACHE="$HOME/.cache/huggingface/hub"
if [ -n "$OFFLINE_SRC" ]; then
  echo "--- 离线模型: $OFFLINE_SRC ---"
  mkdir -p "$MODEL_CACHE"
  cp -r "$OFFLINE_SRC"/models--BAAI--bge-small-zh-v1.5 "$MODEL_CACHE/" 2>/dev/null || {
    echo "⚠ 离线模型目录不匹配, 请提供 huggingface hub 缓存目录结构"; }
else
  echo "--- 下载 embedding 模型 (hf-mirror 优先, 失败回退官方源) ---"
  export HF_ENDPOINT="https://hf-mirror.com"
  uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('$MODEL_NAME')" 2>/dev/null \
    || { echo "镜像失败, 回退官方源..."; export HF_ENDPOINT="https://huggingface.co"; \
         uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('$MODEL_NAME')"; }
fi

# ---------- 4. 密钥配置 (占位, 客户侧替换) ----------
if [ ! -f .env.local ] && [ ! -f ~/.hermes/.env ]; then
  echo "DEEPSEEK_API_KEY=sk-xxxxxxxx（替换为客户 key）" > .env.local
  echo "⚠ 已生成 .env.local 占位 — 请替换 DEEPSEEK_API_KEY (或改用内网 LLM)"
fi

# ---------- 5. 服务注册 + 健康检查 ----------
echo "--- 启动服务 (端口 $PORT) ---"
nohup uv run streamlit run serve_compliance.py --server.port "$PORT" --server.headless true \
  --server.address 0.0.0.0 > "$HOME/pulse-qa.log" 2>&1 &
SVC_PID=$!
echo $SVC_PID > "$HOME/pulse-qa.pid"

for i in $(seq 1 40); do
  if curl -s -m 2 -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT" 2>/dev/null | grep -q 200; then
    echo "✅ 服务就绪: http://localhost:$PORT (${i}x3s)"
    break
  fi
  sleep 3
  [ $i -eq 40 ] && echo "❌ 服务启动超时, 查日志: ~/pulse-qa.log" && exit 1
done

echo ""
echo "=== 部署完成 (耗时 $(($(date +%s) - ${START_TS:-$(date +%s)}))s 内) ==="
echo "  问答界面: http://localhost:$PORT"
echo "  状态检查: curl http://127.0.0.1:$PORT/health"
echo "  停止服务: kill \$(cat ~/pulse-qa.pid)"
echo ""
echo "下一步: 打开页面 → 上传 5 份制度文档 → 自动索引 → 10 分钟出价值仪表盘"
