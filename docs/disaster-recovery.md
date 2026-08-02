# VPS 灾难恢复手册 (Disaster Recovery)

> 用途: VPS 崩溃/到期后, 在新机器 30 分钟内重建全部服务与数据
> 前提: GitHub 仓库完好 (代码/配置/知识已备份)
> 密钥: ~/.hermes/.env 需手动恢复 (值仅存本地保险库, 不在此文档)

---

## 0. 快速恢复时间线

```
0-5 min:   安装基础环境 (python/uv/git)
5-15 min:  克隆 10 个仓库
15-25 min: 恢复 Hermes 配置 (skills/memories/config)
25-30 min: 安装服务 + 重建数据 + 验证
```

## 1. 基础环境

```bash
# Ubuntu 22.04+ (需 4GB+ 内存)
apt update && apt install -y python3.11 python3-pip git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

## 2. 克隆仓库 (10 个)

```bash
mkdir -p /root/projects && cd /root/projects
# Tier 1 (核心)
git clone git@github.com:YYW0228/pulse-data-engine.git
git clone git@github.com:YYW0228/hermes-brain.git
git clone git@github.com:YYW0228/china-ai-governance.git
# Tier 2 (活跃)
git clone git@github.com:YYW0228/job-scraper.git
git clone git@github.com:YYW0228/startalent-enterprise.git
# Tier 3 (存档)
git clone git@github.com:YYW0228/kv-cache-governance.git
git clone git@github.com:YYW0228/my-intelligence-base.git
git clone git@github.com:YYW0228/obsidian_2025.git
git clone git@github.com:YYW0228/SOVEREIGN-SINGULARITY.git
git clone git@github.com:YYW0228/startalent-project-template.git
```

## 3. 恢复 Hermes 配置

```bash
mkdir -p ~/.hermes
# Skills (自研技能)
rsync -a /root/projects/hermes-brain/skills/ ~/.hermes/skills/
# Memories (长期记忆)
rsync -a /root/projects/hermes-brain/memories/ ~/.hermes/memories/
# Config (模型/provider/persona)
cp /root/projects/hermes-brain/profiles/default/config.yaml ~/.hermes/config.yaml
# Cron 任务定义
cp /root/projects/hermes-brain/cron/jobs.json ~/.hermes/cron/ 2>/dev/null
```

## 4. 恢复密钥 (手动, 关键步骤!)

```bash
# 从本地保险库恢复 (密码管理器/加密笔记)
cat > ~/.hermes/.env << 'EOF'
# [手动填入 - 值不在此文档]
DEEPSEEK_API_KEY=...
TELEGRAM_BOT_TOKEN=...
EOF
chmod 600 ~/.hermes/.env
```

## 5. 安装服务 (pulse-data-engine)

```bash
cd /root/projects/pulse-data-engine
uv sync
cp deploy/*.service /etc/systemd/system/
systemctl daemon-reload
make services-start
```

## 6. 重建数据 (源文档 → 索引)

```bash
cd /root/projects/pulse-data-engine
# 合规知识库 (md 文档)
uv run python -m scripts.compliance_index --source /root/projects/china-ai-governance/ai-governance-legal/references --include-jsonl
# 情报报告 (scene2)
uv run python -m scripts.compliance_index --source data/scene2_intel --include-jsonl
# 预计 < 30 分钟 (246 块 + 124 块)
```

## 7. 验证清单

```bash
# 服务健康
uv run python -m scripts.ports --check
# 各端口
curl -s -o /dev/null -w "%{http_code}" http://localhost:8501  # Dashboard
curl -s -o /dev/null -w "%{http_code}" http://localhost:8502  # 合规问答
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/wasm
curl -s -o /dev/null -w "%{http_code}" http://localhost:9464/metrics
# 问答可用
uv run python -m scripts.compliance_qa --query "算法备案的要求"
# CI 状态 (GitHub Actions)
gh run list --repo YYW0228/pulse-data-engine
```

## 8. 密钥清单 (名称 + 用途, 值在本地保险库)

| 密钥 | 用途 | 存储 |
|------|------|------|
| DEEPSEEK_API_KEY | 问答/评审/洞察 LLM | ~/.hermes/.env |
| TELEGRAM_BOT_TOKEN | Telegram 桥 | ~/.hermes/.env |
| GH_TOKEN / SSH key | git push | ~/.ssh/ + gh auth |
| (其他按需) | | |

## 9. 数据重建原理 (为什么数据不丢)

```
DuckDB 二进制 (jobs.duckdb/compliance.duckdb) 不进 git (锁冲突 + 大文件)
但: 源文档全在 GitHub (china-ai-governance md / scene2_intel)
   → 重建 = 跑索引流水线 (脚本化, 可重复)
   → 数据不丢, 只是需要 30 分钟重放
```
