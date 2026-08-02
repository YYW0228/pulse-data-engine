# VPS 数据与 Hermes 配置备份架构 (2026-08-02)

> 目标: VPS 崩溃/到期不丢失数据与配置, 可在新机器 30 分钟内重建
> 原则: 代码/配置/知识 → GitHub (多副本); 密钥 → 仅本地 (重建手册); 数据 → 可重建

---

## 一、备份矩阵 (当前状态 + 检验结果)

| 资产 | 位置 | 备份方式 | 状态 | 检验 |
|------|------|---------|------|------|
| **代码** (10 仓库) | /root/projects/ | GitHub push | ✅ | 5 核心仓库 0 未提交 |
| **Skills** (自研) | ~/.hermes/skills/ | hermes-brain git | ✅ | 已入库 (harness-engineering/devour 等) |
| **Memories** | ~/.hermes/memories/ | hermes-brain git | ✅ | 272 文件已备份 |
| **config.yaml** | ~/.hermes/config.yaml | hermes-brain git | ⚠️ 部分 | profiles/default/config.yaml 有, 但**当前默认配置未同步** |
| **cron 任务** | ~/.hermes/cron/ | hermes-brain git | ✅ | cron/jobs.json + output 已入库 |
| **密钥 .env** | ~/.hermes/.env | ❌ 不进 git (正确) | ✅ | 需重建手册 |
| **DuckDB 数据** | 各项目 data/ | ❌ 二进制不进 git (正确) | ✅ | 源文档在 GitHub, 可重建索引 |
| **systemd 服务** | /etc/systemd/system/ | deploy/*.service 进 git | ✅ | 已备份 |
| **GitHub Actions** | .github/workflows/ | git (天然) | ✅ | CI + Daily Pipeline |

## 二、发现的问题 (检验结论)

```
问题 1: config.yaml 备份不完整
  hermes-brain 只备份了 profiles/default/config.yaml
  但 /root/.hermes/config.yaml (实际生效的) 未同步
  → 新机器重建后模型/provider 配置会丢

问题 2: memories 备份路径混乱
  本地 ~/.hermes/memories/ (MEMORY.md/USER.md) 
  vs 仓库 memories/ (ARCHITECTURE_RULES.md 等知识文件)
  → MEMORY.md/USER.md 是否真的同步? 待确认

问题 3: 无"重建手册"
  密钥清单/服务列表/端口映射/启动顺序 没有单点文档
  → VPS 到期换新机时靠记忆重建, 高风险

问题 4: 备份是手动/半自动
  brain-sync cron 有但依赖 rsync 时机
  无"备份健康检查" (备份失败无告警)
```

## 三、补强方案 (按优先级)

### P0: 重建手册 (今天做) — 新机器 30 分钟重建的完整指南
```
docs/disaster-recovery.md:
  1. 密钥清单 (名称+用途, 值仅本地)
  2. 服务清单 (5 个 systemd 服务 + 端口)
  3. 克隆顺序 + 依赖安装
  4. 数据重建 (源文档 → 索引)
  5. 验证清单 (curl 检查)
```

### P1: config.yaml 完整同步 (今天做)
```
hermes-brain 增加 config sync:
  rsync /root/.hermes/config.yaml → hermes-brain/configs/config.yaml
  (脱敏: 过滤 key/token/secret 行)
```

### P2: 备份健康检查 cron (本周做)
```
新增 cron: 每 24h 检查
  - 各仓库 git status 未提交数 = 0
  - hermes-brain 上次 push 时间 < 48h
  - 5 服务全部 running
  - 失败 → 告警 (Telegram)
```

### P3: 数据可重建验证 (试点前做)
```
验证: 从 GitHub 源文档 → 重建 compliance.duckdb 的完整流程
  记录耗时 (预期 < 30 分钟)
  输出: 重建脚本 scripts/rebuild_all.sh
```

---

## 四、多仓库目标工作区备份策略 (10 仓库分类)

```
Tier 1 (核心, 每日 push): pulse-data-engine / hermes-brain / china-ai-governance
Tier 2 (活跃, 每周 push): job-scraper / startalent-enterprise
Tier 3 (存档, 有改动才 push): kv-cache-governance / my-intelligence-base / obsidian_2025 / SOVEREIGN-SINGULARITY / startalent-project-template

备份频率:
  Tier 1: brain-sync cron (每 30 分钟 skills/memories) + 每日 git push
  Tier 2/3: 每周手动或 cron 检查
```

## 五、新机器重建步骤 (摘要)

```bash
# 1. 安装基础 (uv/python/git)
# 2. 克隆 10 仓库
git clone git@github.com:YYW0228/pulse-data-engine.git
# ... (10 个)
# 3. 恢复 Hermes 配置
rsync -a hermes-brain/skills/ ~/.hermes/skills/
rsync -a hermes-brain/memories/ ~/.hermes/memories/
cp hermes-brain/configs/config.yaml ~/.hermes/config.yaml
# 4. 恢复密钥 (手动, 从本地保险库)
# 5. 安装 systemd 服务
make install-services && make services-start
# 6. 重建数据
uv run python -m scripts.compliance_index --source <docs> --include-jsonl
# 7. 验证
curl localhost:8501 8502 8000 9464
```
