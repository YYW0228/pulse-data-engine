# 素材工厂 — 课程清单 + 操作手册 (Mac mini 本地版)

> 2026-08-27 | 全部本地推理 (whisper.cpp + llama-server Qwen3.5-9B), 零云 API
> 选题来源: course_gaps.yaml (kb_gap 自动) + harness/课程体系推理

## 一、当前队列 (4 选题, 已填候选 URL, 批量生产中)

| 选题 | 课程视频 | 时长 | 理由 (推理依据) |
|------|----------|------|-----------------|
| 提示词工程最佳实践 | Tech With Tim: Prompt Engineering Full Course (2BpCk4d2Cc0) | 38min | course_gap #2; 13节系列缺提示词实操; 客户高频问题 |
| AI智能体入门 | Anthropic: Building more effective agents (uhJJgc-0iTQ) | 19min | course_gap #3; harness 主线 = agent 工程, 官方权威源 |
| RAG评估指标实操 | NeuralNine: Evaluate AI Agents with Ragas (dOKHuw52YTA) | 22min | course_gap #1; RAG 原理素材已有 (08-26 入库), 补评估闭环 |
| 数据飞轮与知识库建设 | Mayuresh: Agent-in-the-Loop Data Flywheel (q0L_EnGlCes) | 7min | course_gap #4; 商业主线知识库资产化 |

## 二、你自己操作 (命令速查)

```bash
# 1. 跑单个视频 (核心命令)
cd ~/projects/pulse-data-engine
uv run python -m scripts.ingest_produce 'https://youtu.be/XXX'
# 可选参数: --lang en (指定语言) --score 8 (自评分)

# 2. 批量消费队列 (approved 且未 done)
uv run python -m scripts.ingest_playlist --queue 'https://youtu.be/xxx'

# 3. 新增选题 → 队列
# 编辑 data/ingest/queue/<选题名>.json:
#   {"slug": "...", "topic": "...", "source": "manual", "priority": 2,
#    "expected_value": 6, "status": "approved", "candidates_urls": ["https://youtu.be/XXX"], ...}
# 或用 --ytsearch 让脚本自动搜候选: ingest_playlist --queue --ytsearch 'https://youtu.be/xxx'

# 4. 查看进度
ls -lt data/ingest/          # 每个视频的处理产物 (json+md)
cat data/ingest/queue/*.json | grep done_at   # 已完成的选题
tail -20 ~/ingest-factory/logs/llamaserver.log  # 本地模型日志
```

## 三、自检 (本地服务状态)

```bash
curl -s http://127.0.0.1:8080/health    # {"status":"ok"} = 本地模型在
ls ~/whisper.cpp/models/ggml-large-v3-turbo.bin  # 转录模型在
launchctl list | grep ingest             # com.ingest.llamaserver 常驻
```

## 四、产物流向 (自动)

```
YouTube 视频 → yt-dlp 下载 (Brave cookies) → whisper.cpp 转录 (本地)
→ llama-server 分段吞噬 → 6 段中文结构素材 (TL;DR/章节摘要+时间戳/概念卡片)
→ data/ingest/ + data/scene2_intel/ingest-*.md
→ kb-refresh 04:00 → 8502 知识库索引 → 客户演示/课程素材可用
```

## 五、资金说明

- 转录: whisper.cpp 本地推理 (M1 免费)
- 翻译/结构化: llama-server Qwen3.5-9B 本地推理 (M1 免费, launchd 常驻)
- 下载: yt-dlp 免费
- **总成本: ¥0/条** — 与 DeepSeek 云 API 对比: 单条 28min 视频约省 ¥0.5-2

## 六、后续选题 (第二批候选, 等队列清空后)

- Karpathy: Intro to Large Language Models (全景, 客户科普用)
- DeepLearning.AI 系列 (和 wharton 课程等 — 需评估时长)
- 提问力/BEST 结构化思考的英文对照源 (课程互证)
- 按 kb_gap 自动建议继续 (kb_gap_weekly cron 输出)
