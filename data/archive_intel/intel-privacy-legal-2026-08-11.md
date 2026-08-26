# 情报简报: privacy-legal

**时间**: 2026-08-11 12:10
**源**: CAC官网/央视网/深圳司法局/Reddit r/LocalLLaMA

## 高相关度发现

- [95pts] **中央网信办"清朗·整治AI应用乱象"专项行动（2026-04-30 启动，为期4个月）** → 第一阶段7类整治重点中 3 项直接命中本项目核心：③大模型训练语料安全（未授权数据入训、来源合规）、⑥滥用AI侵犯隐私（智能体窃取用户数据/账户密钥）、⑦开源模型安全管理（开源社区数据集/模型缺乏审核与应急处置）。对项目的价值：a) 企业客户在本地部署/私有化大模型时对训练数据来源合规与内容安全的合规诉求将显著上升；b) 开源模型供应链（下载/分发数据集）成为监管关注点，契合 sovereign-singularity 吞噬管道的"引用验证/来源合规"设计；c) 供应商审查清单应加入"语料授权证明、开源模型来源审计"检查项。
  来源: https://www.cac.gov.cn/2026-04/30/c_1779289298718765.htm

- [88pts] **《个人信息出境认证办法》2026-01-01 施行 + CAC 2026年1月/7月数据出境政策问答** → 认证路径（非CIIO、10万-100万个人信息或<1万敏感信息）正式落地，与安全评估、标准合同形成三轨；2026年7月问答新增"出境必要性评估"细化（如招聘场景向境外总部传简历：境外不参与录用决策则数据出境不具备必要性）。对项目的价值：AI 治理域数据出境差距分析的合规路径矩阵需更新为三轨制 + 必要性评估先行；为 feynoak/公众号矩阵等涉及境内数据的产品提供出境场景判断模板。
  来源: https://www.cac.gov.cn/2026-01/30/c_1771505108953002.htm ; https://www.sohu.com/a/1054706989_121106832 ; https://news.cctv.com/2025/10/17/ARTIvwIE8sU8riEjK3H0IWXG251017.shtml

## 中相关度

- [70pts] **《人工智能拟人化互动服务管理暂行办法》（2026-04-10 五部门联合公布，2026-07-15 施行）** → 我国首部 AI 拟人化互动服务专门立法（"小快灵"立法）。明确交互数据（私密情感表达）具敏感性、私密性，直接关系人格尊严；划清人机情感交互安全底线。对项目的价值：AI 影响评估模板需新增"情感计算/拟人化互动"数据敏感度评估维度；心理陪伴类产品的 PIA 检查项。
  来源: https://www.cac.gov.cn/2026-06/03/c_1782142434783056.htm

- [65pts] **《汽车数据出境安全指引（2026版）》** → 行业细分指引落地：100万人/1万人敏感信息申报评估门槛、集团合并申报、禁止数量拆分规避。对项目的价值：行业化指引模式可作 AI 治理供应商审查与数据出境模块的参考范式（行业分册思路）。
  来源: https://www.afdata.org.cn/PolicyCountry/0d8b08bd-436b-43a4-abaf-b857bafc19d6

- [60pts] **Reddit: EU inference providers with strong privacy (r/LocalLLaMA, 2026-08 前后)** → 用户寻找"欧盟境内托管开源模型、强隐私保证、按 token 计费"的推理 API，痛点：多数供应商隐私政策含"输入不得含私密数据"免责条款；DeepSeek V3 级大模型可用的 EU 托管选项稀缺。对项目的价值：佐证"本地推理/隐私保证"市场缺口；本地 Qwen 基座 + llama.cpp 路线的差异化叙事素材（隐私条款对比表）。
  来源: https://www.reddit.com/r/LocalLLaMA/comments/1ko1u5c/eu_inference_providers_with_strong_privacy

- [55pts] **Reddit: How do large companies securely integrate LLMs (r/LocalLLaMA)** → 企业以 LLM 作自主代理对接内部系统（ERP/chat）时，数据保密性是首要障碍。对项目的价值：对应本项目"本地化部署 + 数据不出境"价值主张的直接用户痛点证据。
  来源: https://www.reddit.com/r/LocalLLaMA/comments/1oqrn1f/how_do_large_companies_securely_integrate_llms

- [50pts] **Reddit: PII 脱敏进训练数据 (r/LocalLLaMA, How to avoid sensitive data/PII being part of LLM training data)** → 实操讨论：Protegrity 开源版 docker 化 PII 脱敏、联邦学习、最小化/匿名化、GDPR/CCPA/HIPAA 合规引用。对项目的价值：PII 脱敏工具链清单（可并入 AI 治理数据管线建议）。
  来源: https://www.reddit.com/r/LocalLLaMA/comments/18s1lvj/how_to_avoid_sensitive_datapii_being_part_of_llm

## 监管趋势判断

数据出境三轨制落地+认证施行，AI训练语料与开源模型合规成整治重点，监管向场景化"小快灵"立法深化。

## 本期最有价值发现

**"清朗·整治AI应用乱象"专项行动**：中央网信办首次将"大模型训练语料来源合规（未授权数据入训）""智能体窃取用户数据侵犯隐私""开源模型/数据集安全管理"列为全国性专项整治重点，且与《个人信息出境认证办法》施行（2026-01-01）、《人工智能拟人化互动服务管理暂行办法》（2026-07-15 施行）形成"专项整治 + 三轨出境制度 + 场景立法"的组合拳。对 china-ai-governance 的直接意义：企业端 AI 合规需求正从"算法备案"扩展到"训练数据来源审计 + 开源模型供应链管控 + 隐私交互数据治理"，本项目的供应商审查与 AI 影响评估模块应同步纳入这三类检查项，且本地化部署（数据不出境）作为合规解决方案的论证力度应上调。

---
*注: Reddit 线程正文被反爬拦截（登录墙），英文信号基于搜索摘要，置信度中等。*
