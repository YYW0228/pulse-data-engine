# 工作区信息源资产地图 (2026-08-03)

> 目的: 全盘盘点 10 仓库的可延伸/共享能力, 为阶段 B 试点和外部信息获取
> 提供"先从自己有的开始"的资产清单。

---

## 一、信息源采集能力 (可延伸的"信息管道")

### 1. 招聘/人才市场 (job-scraper + pulse)
| 能力 | 位置 | 状态 | 延伸价值 |
|------|------|------|---------|
| BOSS 直聘采集 (API+cookie) | src/crawlers/boss_*.py | ⚠️ WAF 受限 | 市场信号 (低频采样) |
| 猎聘/智联/前程无忧/拉勾 | src/collector.py JOB_SOURCES | ✅ 可用 | 岗位需求洞察 |
| Tavily 搜索 + Firecrawl 抓取 | collector.py 管道 | ✅ 可用 | 通用网页采集 |
| 全链路采集→DuckDB→dbt | collector.py all | ✅ CI 跑通 | 数据管道模板 |

### 2. 法规情报管道 (china-ai-governance)
| 能力 | 位置 | 状态 | 延伸价值 |
|------|------|------|---------|
| 全球 AI 法规情报 (Google+RSS+Reddit) | _intel_scraper_v2.py | ✅ 每日产出 | **自动更新知识库** (护城河) |
| 42 治理文档 + 124 法律分类文档 | ai-governance-legal/ 等 | ✅ 已索引 | 合规知识库源 |
| 中/英双语法律分类 (商业/企业/劳动/IP) | commercial/ corporate/ employment/ ip-legal | ✅ | 多场景知识源 |

### 3. 情报报告库 (pulse data/scene2_intel)
- 37 份 intel 报告 (WAICO/Agent 监管/备案数据/隐私法规) → 已索引 124 块
- **延伸**: 定时重跑 intel_scraper → 新报告 → 增量索引 → 知识库自动保持最新

### 4. 知识库 (obsidian_2025 + hermes-brain)
- obsidian_2025: 749 md (OpenClaw/研究/知识管理)
- hermes-brain: 1310 文档 + 771 源码 (skills/memories/config 全备份)

## 二、可共享的功能组件 (跨项目复用)

### 框架层 (pulse-data-engine, 已验证可复制)
```
1. compliance_index.py — 任意 md/jsonl → 向量索引 (增量替换)
2. compliance_qa.py    — 检索→编译→路由→回答 (零改动换数据)
3. doc_parser.py       — PDF/Word/md/txt → 标准块
4. artifacts.py        — 证据包 (可验收交付)
5. vector_store.py     — DuckDB/Qdrant 抽象 (换后端零改动)
6. trace.py / metrics.py — 可观测 + 成本核算
7. memory.py           — WAL/冲突/遗忘/提取/合并
```

### 采集层 (job-scraper)
```
1. collector.py 全链路管道 (采集→清洗→DuckDB→洞察)
2. crawlers/boss_* 反检测技术 (cookie 管理/stealth)
3. analyzers/ LLM 结构化洞察
```

### 治理层 (china-ai-governance)
```
1. 法规情报管道 (自动更新)
2. 42 治理文档 + 分类法律库 (知识源)
3. dbt 模型 (数据转换模板)
```

### 商业层 (startalent-enterprise)
```
1. talent-engine 采集 + 课程 (L4 课程资产)
2. ods-extension API + gen_ai_pm_radar (市场雷达)
3. cross_repo_trigger (跨仓库联动)
```

## 三、外部信息源获取方案 (从自己有的开始)

### 已拥有的信息管道 (可直接复用)
| 信息源 | 管道 | 输出 | 频率 |
|--------|------|------|------|
| 招聘网站 (5源) | job-scraper | 岗位数据 | 周/低频 |
| 全球 AI 法规 | intel_scraper_v2 | 情报报告 | 每日 |
| Google/RSS/Reddit | intel_scraper | 原始发现 | 每日 |
| Tavily/Firecrawl | collector.py | 网页内容 | 按需 |

### 可延伸的新信息源 (用现有管道扩展)
| 新源 | 复用管道 | 改动量 |
|------|---------|--------|
| 政府法规站 (工信部/网信办) | intel_scraper_v2 加 URL | 小 (加源) |
| 行业报告 (艾瑞/亿欧) | Firecrawl 采集 | 小 (加源) |
| 学术 (arXiv) | obsidian 已有 arxiv skill | 小 (已有) |
| 社交媒体 (抖音/小红书) | 未建 (需评估合规) | 中 |
| 企业官网 | Firecrawl 批量 | 小 |

### 信息源延伸原则
```
1. 先复用已有管道 (加 URL/加源), 不新建
2. 低频 + 人工抽检 (数据质量 > 数量)
3. 合规优先 (ToS 检查)
4. 情报→知识库→问答闭环 (intel → index → QA)
```

## 四、阶段 B 可延伸资产清单 (试点直接用)

| 资产 | 位置 | 试点用途 |
|------|------|---------|
| 数据接入标准包 | pulse docs/data-onboarding-kit.md | 客户文档接入流程 |
| 演示脚本 | pulse scripts/demo_run.py | 现场演示 |
| 一页纸案例 | pulse docs/sales-one-pager.md | 销售弹药 |
| 框架复刻验证 | pulse docs/audit-vps-framework-compliance.md | 能力证据 |
| 情报自动更新 | china-ai-governance intel_scraper | 知识库保鲜卖点 |
| 部署选项 | pulse docs/deployment-options.md | 私有化方案 |
| 定价模型 | pulse docs/pricing-model.md | 商务谈判 |

## 五、建议延伸优先级 (按 ROI)

```
P0 (本周可做):
  1. intel_scraper → cron 定时跑 → 知识库自动更新 (护城河实证)
  2. 新增 2-3 个法规源 URL (网信办/工信部) → 情报更全

P1 (试点前):
  3. 企业制度文档模板化 (用 scene3_policy 经验做标准模板)
  4. 每客户单独索引库脚本 (data-isolation 工具)

P2 (规模化):
  5. 行业报告采集 (Firecrawl 扩展)
  6. 学术论文管道 (arXiv skill 接入知识库)
```
