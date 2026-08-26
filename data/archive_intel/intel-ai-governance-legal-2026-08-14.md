# 情报简报: ai-governance-legal

**时间**: 2026-08-14
**源**: CAC官网(beian.cac.gov.cn)/中文新闻/Reddit

**速答**: 本期核心信号 = 算法备案**注销机制常态化**——beian.cac.gov.cn 置顶显示 2026 年内已发布 3 次注销公告（3/12 注销"书链鲸咕噜大模型算法"等、5/6 注销"生成无限多模态大模型算法-1"等 5 个、7/17 注销"云智手机生成式算法"等 **10 个**），单次注销规模递增。监管从"准入备案"走向**全生命周期管理**（备案/变更/注销三环节闭环）。新增批次同步推进：深度合成第 18 批（2026-07-17）、生成式AI累计 988 款备案（7/10 公告，上期已报）。项目供应商审查与 AI 影响评估模板须新增**备案状态核查**（含注销/失效风险）检查点。

## 高相关度发现

- [85pts] 算法备案注销公告 2026 年 3 连发、规模递增（3/12 → 5/6 注销5个 → 7/17 注销10个）→ **备案生命周期合规是新盲区**：供应商审查模板此前只查"是否备案"，未查"备案是否仍有效/被注销"；被注销=服务终止或合规失效，直接影响供应链 AI 依赖的持续性尽调。beian.cac.gov.cn 公告区为官方一手来源。
  - https://beian.cac.gov.cn （置顶公告区：注销"云智手机生成式算法"等10个算法备案编号的公告 2026-07-17；注销"生成无限多模态大模型算法-1"等5个 2026-05-06；注销"书链鲸咕噜大模型算法"等 2026-03-12）

- [70pts] 第十八批深度合成服务算法备案公告（2026-07-17，网信办）正文核验完成，附件=境内深度合成服务算法备案清单（2026年7月），含下载直达链接 → 上一期仅记录批次号，本期补充附件 URL，名单类数据缺口可从此附件抓取（科大讯飞/字节等厂商在列情况可查）。
  - 公告: https://xinwen.bjd.com.cn/content/s6a5a0689e4b0e45f3fd4cbb6.html
  - 附件: https://www.cac.gov.cn/cms/pub/interact/downloadfile.jsp?filepath=NUtqEIwGiCjGm2Bhl20cvMov5mYBGwhXUVM72KjtgTcN0FupMe0gVPpTdbz/hKvNhR7lj13iAyvcOy2KRBQcfjZS2/Bjnic3oqu3HpPj8kk=

## 中相关度

- [55pts] Reddit r/LocalLLaMA: "Why aren't any American open-source AI labs even close to Chinese ones on benchmarks yet?"（170 upvotes / 209 comments，约27天前）→ 英文社区对中国开源模型生态的高热度讨论；虽非监管议题，但反映"中国AI实力"叙事升温，可作国际侧背景素材（与 CN 合规框架并存的产业竞争力叙事）。
  - https://www.reddit.com/r/LocalLLaMA/comments/1qsz1p3/ 同帖列表页含该话题；原帖 https://www.reddit.com/r/LocalLLaMA/comments/1qy5x2i/ （基于搜索摘要，未核验全文）

- [45pts] Reddit r/LocalLLaMA: "Anthropic is deploying $20M to support AI regulation in sight of 2026 elections" → 美国侧监管游说动向，与 CN 行政备案制形成对照（美=选举周期政治博弈，中=行政准入+全生命周期清退），用于监管态势对比分析。
  - https://www.reddit.com/r/LocalLLaMA/comments/1r7fb2k/

- [40pts] 生成式AI备案时间线补全：CAC 2026-05-13 公告显示 2026年3-4月新增备案72款、登记49款，截至4/30累计 **868款备案 / 530款登记** → 与 7/10 公告的 988款/598款 衔接，可得月度扩容节奏（约月均+30-60款），支撑备案趋势分析数据链。
  - https://www.cac.gov.cn/2026-05/13/c_1780413225190669.htm （正文已核验）

- [35pts] 第三方实操帖：2026 算法备案采用"一审+二审"双审机制，新增 API 调用场景界定，7 月起执行 11 项新国标（CSDN 2026 完整版教程）→ 与上期 40pts 条目同源类信息（材料趋严、风险分级），本期不重复计分，仅作实务要点存证；第三方口径，须官方核验后方可入交付物。
  - https://blog.csdn.net/cao919/article/details/163293861

## 监管趋势判断

备案进入"扩容+清退"双轨：批次新增常态化（累计近千款），注销机制同步收紧，监管覆盖备案全生命周期。

## 最有价值发现

**算法备案注销常态化（2026-07-17 单次注销 10 个算法备案编号）**——监管已完成从"备案准入"到"备案后治理"的闭环：注销即服务终止或合规失效，供应商的 AI 依赖可能因上游备案被注销而断裂。项目供应商审查模板与 AI 影响评估需新增"备案状态核查（有效/变更/注销）"检查点，并建立被注销主体名单跟踪机制。
