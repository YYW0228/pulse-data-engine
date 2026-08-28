# 情报简报: privacy-legal

**时间**: 2026-08-14
**源**: CAC官网 / 江苏网信网 / 福建商务厅 / 安全内参 / Reddit r/LocalLLaMA

## 高相关度发现

- [9pts] **《数据出境安全管理政策法规问答（2026年7月）》**（CAC 官方最新一期问答, 2026-07-24）→ 两个实操要点: ① 个人信息出境须履行告知+单独同意（PIPL §39/§30）, 禁止"一揽子"授权, 参照 GB/T 42574-2023; ② 安全评估结果有效期 3 年, 到期前 60 个工作日内可申请延长 3 年, 条件含自然人数量增幅 ≤20%、法律文件合规、无重大安全事件。→ 项目可直接作为数据出境合规工作流的事实依据（阈值与期限均为最新口径）。 https://www.jswx.gov.cn/shuju/zixun/202607/t20260724_1346737.shtml
- [8pts] **"清朗·整治AI应用乱象"专项行动**（CAC, 2026-04-30, 为期4个月）→ 第一阶段 7 类整治含: 大模型"应备未备"、训练语料来源不合规/未授权数据、AI数据投毒、开源模型社区无审核机制、智能体窃取用户数据/账户密钥。→ 直接对应本地大模型部署合规审查清单（备案义务+训练数据来源验证+开源模型安全评估）。 https://www.cac.gov.cn/2026-04/30/c_1779289298718765.htm
- [7pts] **《数据出境安全管理政策法规问答（2026年1月）》**（CAC 官方）→ 明确标准合同/认证与安全评估的衔接阈值: 10万-100万个人信息(非敏感)或<1万敏感信息走标准合同/认证; 超 100万个人信息或超 1万敏感信息必须申报安全评估; 大湾区标准合同不得向区外提供。→ 项目"数据出境合规路径判定"逻辑的权威依据。 https://www.cac.gov.cn/2026-01/30/c_1771505108953002.htm
- [6pts] **Reddit: "How do large companies securely integrate LLMs without..."**（r/LocalLLaMA）→ 企业把 LLM 接入 ERP/内部系统的最大障碍是数据保密性; 社区共识=敏感数据不出本机/私有部署。→ 佐证本地推理作为企业合规方案的海外需求端信号。 https://www.reddit.com/r/LocalLLaMA/comments/1oqrn1f/how_do_large_companies_securely_integrate_llms

## 中相关度

- [5pts] **《汽车数据出境安全指引(2026版)》**（工信部等八部门, 2026-02）→ 行业级细则范例: 重要数据分场景判定、9类免申报情形(含安全漏洞/OTA源代码)、不得拆分申报; 申报不要求提交原始数据, 只报类型/规模特征。→ 可作其他行业数据出境指引的结构模板。 https://policy.mofcom.gov.cn/claw/policyInfo.shtml?id=8728
- [5pts] **Reddit: "Are local LLMs private and secure?"**（r/LocalLLaMA）→ 核心观点: 模型本身只是数据, 隐私取决于运行它的软件栈; 仅靠本地部署≠安全。→ 提示本地推理方案必须附带运行时安全审查, 契合项目"本地部署≠自动合规"立场。 https://www.reddit.com/r/LocalLLaMA/comments/1mruuy1/are_local_llms_private_and_secure
- [4pts] **Reddit: "EU inference providers with strong privacy"**（r/LocalLLaMA）→ 用户寻找 EU 境内、隐私保证强的开源权重推理 API 失败: 供应商隐私条款普遍含"输入不得含私密数据"免责。→ 印证自托管是隐私刚需场景的唯一可靠路径。 https://www.reddit.com/r/LocalLLaMA/comments/1ko1u5c/eu_inference_providers_with_strong_privacy
- [4pts] **《促进和规范数据跨境流动规定》实施两周年回顾**（福建商务厅转载中新网, 2026-03）→ 制度面: 2025-10《个人信息出境认证办法》落地; 2025-04 金融业跨境合规指南; 2026-02 汽车指引; 中欧/中德/东盟机制性对话推进互认。→ "负面清单+认证+行业指南"三线并进的趋势确认。 https://swt.fujian.gov.cn/xxgk/jgzn/jgcs/zmsyqzcyjs/zmzcc_gzdt/202603/t20260327_7116292.htm
- [4pts] **Reddit: "10x Inference Tax" 基准帖**（r/LocalLLaMA）→ 蒸馏小模型(Qwen3 0.6B-8B)在 PII Redaction 等 9 个任务上与前沿中档模型打平/超越; PII 脱敏被列为标准评测维度。→ 本地小模型承担 PII 脱敏任务的可行性数据点。 https://www.reddit.com/r/LocalLLaMA/comments/1rjsqa2/benchmarks_the_10x_inference_tax_you_dont_have_to
- [3pts] **国家安全部: 数据出境要注意安全**（安全内参转载）→ 明确出境管理仅限重要数据+个人信息(匿名化除外), 敏感个人信息定义; 强调跨境传输间谍窃密风险防范。→ 补充监管执行侧口径。 https://www.secrss.com/articles/74044
- [3pts] **Reddit: "Prompt injection is killing our self-hosted LLM deployment"**（r/LocalLLaMA）→ 自托管 LLM+工具(如 MCP 访问客户数据)的最大风险是提示注入; 建议: 工具调用令牌必须经用户认证校验, 不可由模型自证。→ 本地推理方案的必备安全设计点。 https://www.reddit.com/r/LocalLLaMA/comments/1qyljr0/prompt_injection_is_killing_our_selfhosted_llm
- [3pts] **"小快灵"立法规范 AI 拟人化互动服务**（CAC 评论文章, 2026-06-03）→ 拟人化 AI 交互数据被认定具有敏感性、私密性, 直接关系人格尊严; 暗示该类服务将面临专门监管。→ 新兴 AI 服务场景的隐私合规前瞻。 https://www.cac.gov.cn/2026-06/03/c_1782142434783056.htm

## 监管趋势判断

数据出境制度体系趋于成熟细化: 认证办法落地、行业指引频出、国际互认推进; AI 训练语料与备案进入专项整治; 本地化部署与隐私保护获得监管与市场双重背书。

---

## 本期最有价值发现

**CAC 2026年7月数据出境问答**（9pts）: 首次系统澄清"告知+单独同意"实操标准（禁止一揽子授权、参照 GB/T 42574-2023）与安全评估延期条件（60个工作日窗口、20%增幅上限）——这是项目数据出境合规工作流可以直接落为检查项的最新官方口径, 且该系列每季度更新, 建议 cron 持续追踪 CAC"数据出境安全管理政策法规问答"系列。
