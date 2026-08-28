# 情报简报: privacy-legal

**时间**: 2026-08-28
**源**: CAC官网/中国网信网/江苏网信网/金杜律所/Reddit r/LocalLLaMA

## 高相关度发现

- [90pts] **《数据出境安全管理政策法规问答（2026年7月）》**（中国网信网, 2026-07-24）→ 官方最新实务口径: 出境告知同意须"具体明确、不得捆绑、不得一揽子授权"(参照 GB/T 42574-2023); 安全评估结果有效期3年, 延期六大条件(目的/主体不变、自然人数量增幅≤20%、法律文件合规、3年无重大安全事件)。对项目价值: 客户跨境业务(外贸场景)的合规咨询直接引用口径。URL: https://www.jswx.gov.cn/shuju/zixun/202607/t20260724_1346737.shtml
- [85pts] **《促进和规范数据跨境流动规定》实施两周年总结**（2026-03-27）→ 数据出境预评估试点由6省扩至14省(新增吉林/安徽/福建/山东/广西/海南/云南/重庆); 3家个人信息出境认证机构完成备案、认证备案系统上线; 金融业跨境合规指南(2025-04)+汽车数据出境指引2026版(2026-02)落地; 中欧数据跨境机制第二次会议。对项目价值: 认证路径制度化+预评估提速 = 客户合规成本下降, 本地部署+合规咨询产品有增量空间。URL: https://swt.fujian.gov.cn/xxgk/jgzn/jgcs/zmsyqzcyjs/zmzcc_gzdt/202603/t20260327_7116292.htm
- [80pts] **"清朗·整治AI应用乱象"专项行动**（CAC, 2026-04-30, 为期4个月两阶段）→ 7类重点: 大模型应备未备、训练语料来源不合规/未授权数据、AI数据投毒(GEO)、开源模型安全管理不到位(社区数据集/模型代码无审核机制)。对项目价值: 本地大模型部署客户的开源模型选型+语料合规直接踩中执法红线, 是治理交付物的核心检查项。URL: https://www.cac.gov.cn/2026-04/30/c_1779289298718765.htm
- [75pts] **《个人信息出境认证办法》**（网信办+市监总局令第20号, 2025-10-17公布, 2026-01-01施行）→ PIPL第38条第三法定路径落地: 非CIIO+10万-100万人(不含敏感)/不满1万敏感个人信息可通过认证出境, 禁止数量拆分规避安全评估。对项目价值: 三条合规路径(评估/标准合同/认证)体系完整, 供应商审查与差距分析需纳入认证条款。URL: https://www.cac.gov.cn/2025-10/17/c_1762449728720008.htm
- [70pts] **《政务领域人工智能大模型部署应用指引》**（CAC, 2025-10-10）→ "涉密不上网、上网不涉密"; 敏感信息禁止输入非涉密模型; 防提示词注入/资源消耗攻击; 日志审计。对项目价值: "本地部署=数据不出域"的制度背书, 可作销售叙事与差距分析基准。URL: https://www.cac.gov.cn/2025-10/10/c_1761819469929310.htm
- [70pts] **r/LocalLLaMA: Are local LLMs private and secure?** → 社区共识: LLM 本身不联网不上传, 本地推理=隐私边界; 讨论仍聚焦"LLM 无网络能力≠周边工具链安全"。对项目价值: 验证"本地部署=数据主权"需求真实存在, 支撑客户价值主张; 提示交付物需覆盖工具链/API 网关审计。URL: https://www.reddit.com/r/LocalLLaMA/comments/1mruuy1/are_local_llms_private_and_secure

## 中相关度

- [65pts] **《智能体规范应用与创新发展实施意见》**（CAC, 2026-05-08）→ 智能体数据安全/个人信息保护/权限管控列为内生安全能力, 防数据投毒、隐私泄露。对项目价值: 智能体是新监管面, 未来客户治理范围扩展。URL: https://www.cac.gov.cn/2026-05/08/c_1779979789523320.htm
- [60pts] **r/LocalLLaMA: How do large companies securely integrate LLMs without leaking confidential data?** → 企业用 LLM agent 接 ERP/内部系统的头号障碍是数据机密性。对项目价值: 与外贸客户 AI 化主攻方向直接呼应, 是本地部署方案的核心卖点证据。URL: https://www.reddit.com/r/LocalLLaMA/comments/1oqrn1f/how_do_large_companies_securely_integrate_llms
- [55pts] **r/LocalLLaMA: Which model providers offer the most privacy?** → 机密/个人/医疗数据处理者默认排除云端供应商。对项目价值: 隐私优先市场细分确认。URL: https://www.reddit.com/r/LocalLLaMA/comments/1ki4pme/which_model_providers_offer_the_most_privacy
- [50pts] **r/LocalLLaMA: LLM-based PII detection tool** → 开源 PII 检测小工具(日志/文本中的个人信息识别)。对项目价值: 可作客户交付物(数据扫描)参考组件。URL: https://www.reddit.com/r/LocalLLaMA/comments/1kn810l/llm_based_personally_identifiable_information
- [50pts] **"小快灵"立法规范 AI 拟人化互动服务**（CAC, 2026-06-03）→ 拟人化交互涉及私密情感数据, 拟出新办法划安全底线。对项目价值: 交互数据敏感面扩大, 隐私影响评估范围更新。URL: https://www.cac.gov.cn/2026-06/03/c_1782142434783056.htm
- [45pts] **r/LocalLLaMA: EU inference providers with strong privacy** → 欧盟云推理供应商隐私条款普遍含"输入不应含私密数据"免责, 无强隐私推理 API。对项目价值: 全球范围"云推理≠隐私"共识, 本地推理差异化论据。URL: https://www.reddit.com/r/LocalLLaMA/comments/1ko1u5c/eu_inference_providers_with_strong_privacy
- [40pts] **r/LocalLLaMA: offline AI for sensitive data processing (银行流水 PDF→CSV)** → 敏感金融单据离线处理需求(本地 LLM 解析)。对项目价值: 外贸客户单据/流水处理场景的落地形态佐证。URL: https://www.reddit.com/r/LocalLLaMA/comments/1lvm3tl/offline_ai_for_sensitive_data_processing_like
- [40pts] **金杜: 数据出境监管"3+1=4"体系解读**(含自贸区负面清单全量梳理) → 律所实务指南, 含大湾区标准合同衔接细节。对项目价值: 供应商审查/法规差距分析的参考素材。URL: https://www.kingandwood.com/cn/zh/insights/latest-thinking/china-s-cross-border-data-transfer-supervision-system-and-the-measures-for-certification-of-personal-information-export.html
- [35pts] **2025 网信大事回眸·网络安全篇**（2025-12-31）→ 《个人信息保护合规审计管理办法》(2025-05-01施行) + 查处82款违法违规 App。对项目价值: 合规审计已入执法工具, 客户审计需求上升。URL: https://www.cac.gov.cn/2025-12/31/c_1768735141277082.htm

## 监管趋势判断

数据出境三条路径制度化完毕、预评估扩至14省提速放行; 大模型语料/开源模型安全成执法重点; 合规审计与认证进入落地执行期。

## 最有价值发现

**《数据出境安全管理政策法规问答（2026年7月）》** — 国家网信办最新实务口径(评估延期六大条件+告知同意落地要求)。它把跨境合规从"原则"落成"可核查条件", 且与 Reddit 侧"本地推理=隐私保护"共识形成互补: 监管侧出境越严、技术侧本地化越强, 恰恰构成本地大模型部署+数据合规治理服务的双轮需求叙事 — 对客户可直接转化为: 数据不出境即可规避评估/认证/标准合同全链条义务。
