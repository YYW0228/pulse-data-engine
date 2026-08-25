#!/bin/bash
# ============================================================
# deploy_macmini.sh — Mac mini 素材工厂一键部署 (7×24)
# 用法: 在 Mac mini 上执行:  bash deploy_macmini.sh [--no-llama]
# 依赖前置: 已安装 Homebrew
# ============================================================
set -euo pipefail

echo "=== Mac mini 素材工厂部署 ==="

# ---------- 0. 路径 ----------
INSTALL_DIR="${INGEST_HOME:-$HOME/ingest-factory}"
WHISPER_DIR="$HOME/whisper.cpp"
MODELS_DIR="$WHISPER_DIR/models"
GIT_REPO="https://github.com/YYW0228/pulse-data-engine.git"
REPO_DIR="$HOME/projects/pulse-data-engine"

# ---------- 1. yt-dlp + ffmpeg ----------
if ! command -v yt-dlp >/dev/null; then
  echo "--- 安装 yt-dlp ---"
  brew install yt-dlp ffmpeg 2>/dev/null || pipx install yt-dlp 2>/dev/null || {
    curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos -o "$HOME/.local/bin/yt-dlp"
    chmod +x "$HOME/.local/bin/yt-dlp"
  }
fi

# ---------- 2. Brave 登录检查 (cookies 通道) ----------
if [ ! -d "$HOME/Library/Application Support/BraveSoftware/Brave-Browser" ]; then
  echo "⚠ 未检测到 Brave 浏览器 — 请先安装 Brave 并登录 YouTube 一次 (cookies 通道必需)"
fi

# ---------- 3. whisper.cpp + turbo 模型 ----------
if [ ! -f "$WHISPER_DIR/build/bin/whisper-cli" ]; then
  echo "--- 编译 whisper.cpp ---"
  git clone https://github.com/ggerganov/whisper.cpp "$WHISPER_DIR" 2>/dev/null || true
  (cd "$WHISPER_DIR" && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j --config Release)
fi

if [ ! -f "$MODELS_DIR/ggml-large-v3-turbo.bin" ]; then
  echo "--- 下载 ggml-large-v3-turbo (1.5G, 需网络通畅) ---"
  mkdir -p "$MODELS_DIR"
  (cd "$MODELS_DIR" && "$WHISPER_DIR/models/download-ggml-model.sh" large-v3-turbo)
fi

# ---------- 4. llama.cpp + Qwen3.5-9B ----------
if ! command -v llama-server >/dev/null; then
  echo "--- 安装 llama.cpp (brew) ---"
  brew install llama.cpp
fi
MODEL_GGUF="$HOME/ODS/data/models/Qwen3.5-9B-Q4_K_M.gguf"
if [ ! -f "$MODEL_GGUF" ]; then
  echo "⚠ 未找到 $MODEL_GGUF — 请从 M2 Max 复制该文件 (或改用其它 GGUF 并改本脚本 MODEL_GGUF)"
fi

# ---------- 5. 私有仓 clone + ingest 脚本 ----------
if [ ! -d "$REPO_DIR/.git" ]; then
  echo "--- clone pulse-data-engine (私有仓) ---"
  mkdir -p "$HOME/projects"
  git clone "$GIT_REPO" "$REPO_DIR"
fi
chmod +x "$REPO_DIR/scripts/ingest_produce.py" "$REPO_DIR/scripts/ingest_playlist.py" "$REPO_DIR/scripts/ingest_review.py" 2>/dev/null || true

# ---------- 6. llama-server launchd 常驻 (7×24) ----------
if [ ! -f "$HOME/Library/LaunchAgents/com.ingest.llamaserver.plist" ]; then
  echo "--- 配置 llama-server launchd 常驻 (--ctx-size 8192, 单并发防内存抖动) ---"
  mkdir -p "$HOME/Library/LaunchAgents" "$HOME/ingest-factory/logs"
  cat > "$HOME/Library/LaunchAgents/com.ingest.llamaserver.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.ingest.llamaserver</string>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/llama-server</string>
    <string>-m</string><string>${MODEL_GGUF}</string>
    <string>--host</string><string>127.0.0.1</string>
    <string>--port</string><string>8080</string>
    <string>-c</string><string>8192</string>
    <string>--parallel</string><string>1</string>
    <string>--mlock</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>${HOME}/ingest-factory/logs/llamaserver.log</string>
  <key>StandardErrorPath</key><string>${HOME}/ingest-factory/logs/llamaserver.err</string>
</dict>
</plist>
PLIST
  launchctl load "$HOME/Library/LaunchAgents/com.ingest.llamaserver.plist"
fi

# ---------- 7. zshrc 对齐 ----------
if ! grep -q WHISPER_CPP_DIR "$HOME/.zshrc" 2>/dev/null; then
  echo 'export WHISPER_CPP_DIR="$HOME/whisper.cpp"' >> "$HOME/.zshrc"
  echo "--- WHISPER_CPP_DIR 已加入 ~/.zshrc (新终端生效) ---"
fi

echo ""
echo "=== 部署完成 ==="
echo "  whisper-cli : $WHISPER_DIR/build/bin/whisper-cli"
echo "  模型        : $MODELS_DIR/ggml-large-v3-turbo.bin"
echo "  llama-server: 127.0.0.1:8080 (launchd 常驻, 单并发+8K ctx)"
echo "  脚本        : $REPO_DIR/scripts/ingest_produce.py"
echo ""
echo "自检:"
curl -s -m 5 http://127.0.0.1:8080/health && echo "  → llama-server OK" || echo "  → llama-server 未就绪 (等 30s 后重试)"
"$WHISPER_DIR/build/bin/whisper-cli" --help >/dev/null 2>&1 && echo "  → whisper-cli OK" || echo "  → whisper-cli 异常"
echo ""
echo "使用:"
echo "  cd $REPO_DIR && uv run python -m scripts.ingest_produce 'https://youtu.be/XXX'"
echo "  cd $REPO_DIR && uv run python -m scripts.ingest_playlist 'https://www.youtube.com/playlist?list=XXX' --dry-run"
