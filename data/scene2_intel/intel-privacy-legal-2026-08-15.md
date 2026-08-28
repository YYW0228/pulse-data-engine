# 情报简报: privacy-legal

**时间**: 2026-08-15 (合并 00:32 + 12:00 两轮采集)
**源**: CAC官网/中国网信网/江苏网信网/科技日报/工信部/Reddit r/LocalLLaMA

速答: 本期监管主线=数据出境制度体系闭环（认证办法2026-01-01施行、评估3年+3年续期细则、汽车行业指引落地）+ 执法重心转向AI训练语料/开源模型供应链（清朗·整治AI应用乱象4个月专项行动）; 海外信号=企业自托管LLM的机密性需求真实但 prompt injection 无100%防线, 本地=绝对隐私的叙事受社区质疑。

## 高相关度发现

- [95pts] 《大型网络平台个人信息保护规定（征求意见稿）》全文（网信办+公安部, 2025-11-22）→ 大型平台认定标准（注册用户5000万+/月活1000万+）、个人信息保护负责人须中国籍管理层并享**否决权**、个人信息**境内存储+境内数据中心**（主要负责人中国籍）、第三方合规审计强制触发情形（100万人以上泄露即触发）。→ 对项目价值: 供应商审查与法规差距分析新增完整条款级依据; 客户若属大型平台, 本地化存储要求直接利好"本地大模型部署"方案。需跟踪正式稿进展。
  URL: https://www.cac.gov.cn/2025-11/22/c_1765543463511624.htm

- [90pts] 中央网信办"清朗·整治AI应用乱象"专项行动（2026-04-30, 为期4个月, 两阶段7+7类问题）→ 第一阶段直接点名: 大模型**备案登记义务**（应备未备）、**训练语料安全**（来源合规、未经授权数据）、**AI数据投毒**（GEO恶意营销）、**开源模型安全管理不到位**（开源社区无身份认证、数据集/模型无审核清理机制）、智能体窃取用户数据。→ 对项目价值: 本地大模型客户的开源模型来源治理成为执法焦点; AI影响评估/算法备案审查的清单项必须补充"开源模型供应链合规"; 智能体隐私风险进入监管视野, 与 confidential computing 卖点强相关。
  URL: https://www.cac.gov.cn/2026-04/30/c_1779289298718765.htm

- [85pts] 数据出境安全管理政策法规问答（2026年7月, 中国网信网/江苏网信网转载）→ 最新实操口径: 出境告知同意须**单独同意、不得捆绑、不得"一揽子"授权**（参考GB/T 42574-2023）; 敏感信息出境须告知必要性+权益影响; 安全评估结果**有效期3年可延3年**, 条件含未来三年自然人数量增幅≤20%、有效期届满前60个工作日内申请。→ 对项目价值: 数据出境合规审查的最新执行标准; 客户评估到期续期窗口是顾问服务触发点。
  URL: https://www.jswx.gov.cn/shuju/zixun/202607/t20260724_1346737.shtml

- [80pts] 《汽车数据出境安全指引（2026版）》八部门联合印发（2026-02, 工信部牵头）→ 行业级出境细则: 100万+个人信息/1万+敏感信息/重要数据→申报安全评估; 10万-100万个人信息/不满1万敏感信息→标准合同或认证二选一; **九类免于申报情形**含安全漏洞/安全事件/OTA升级软件包源代码等重要数据（需向工信部、市场监管总局报告备案）; 明确不得数量拆分规避评估; 申报不要求提交数据本身（只提供特征）。→ 对项目价值: 行业细分指引样本, 汽车/制造类客户的出境合规路径可直接套用; "特征而非原始数据"申报口径利好数据最小化方案设计。
  URL: https://policy.mofcom.gov.cn/claw/policyInfo.shtml?id=8728

- [75pts] 《个人信息出境认证办法》2026-01-01施行, 标志数据出境制度体系构建完成（科技日报, 2025-11-03）→ 10万-100万个人信息/1万以下敏感信息区间, 标准合同与认证二选一; 认证=第三方审核+持续监督+可执行承诺救济。→ 对项目价值: 合规路径三选一（评估/合同/认证）完整落地, 差距分析工具应支持认证路径判定。
  URL: https://www.stdaily.com/web/gdxw/2025-11/03/content_425682.html

## 中相关度

- [60pts] 数据出境安全管理政策法规问答（2026年1月, CAC官网）→ 标准合同/认证与安全评估衔接口径: 自当年1月1日起累计出境10万-100万个人信息（不含敏感）/不满1万敏感信息→标准合同或认证; 超过100万/1万敏感→必须申报安全评估且此前合同/认证出境量纳入申报范围; 粤港澳大湾区标准合同仅限区内流动, 向区外提供须按国家规定履行评估/合同/认证。→ 对项目价值: 阈值衔接规则是跨境合规审查的量化判定依据。
  URL: https://www.cac.gov.cn/2026-01/30/c_1771505108953002.htm

- [60pts] 《促进和规范数据跨境流动规定》实施两周年总结（2026-03-27, 中国新闻网）→ 2025-10 认证办法、2025-04 金融业数据跨境合规指南、2026-02 《汽车数据出境安全指引(2026版)》; 中欧数据跨境交流机制第二次会议、与东盟联合对照指南。→ 行业细分指引密集出台, 客户行业化合规需求上升。
  URL: https://swt.fujian.gov.cn/xxgk/jgzn/jgcs/zmsyqzcyjs/zmzcc_gzdt/202603/t20260327_7116292.htm

- [55pts] 跨境数据流动安全评估整改机制研究（法学论文, 2026-01）→ 披露数据出境申报**通过率仅约1%**（29家通过 vs 千余件申报）; 企业整改机制操作指引模糊、反复提交。→ 对项目价值: 合规失败率极高的量化佐证, 顾问服务ROI叙事可用。
  URL: https://pdf.hanspub.org/ojls_2924029.pdf

- [50pts] Reddit: "does running locally actually protect you or are we kidding ourselves" (r/LocalLLaMA, 2026) → 社区对"本地=绝对隐私"的核心质疑: 威胁模型取决于机器本身是否被攻破、数据是否比存着更危险; 本地运行不是万能药, 需结合磁盘加密/访问控制。→ 对项目价值: 本地部署价值主张必须诚实呈现威胁模型边界, 建议纳入 on-device 方案的风险话术与 FAQ。
  URL: https://www.reddit.com/r/LocalLLaMA/comments/1qpj8q7/does_running_locally_actually_protect_you_or_are

- [50pts] Reddit: "How do we know that local LLMs guarantee privacy" (r/LocalLLaMA) → 核心讨论: 本地推理的隐私保证依赖推理软件本身受信任、需切断 call-home 通道; 社区对"本地=绝对隐私"有质疑。→ 对项目价值: 本地部署价值主张需回应"推理引擎供应链信任"问题, 建议纳入 on-device 方案的风险话术。
  URL: https://www.reddit.com/r/LocalLLaMA/comments/1s5vywn/how_do_we_know_that_local_llms_guarantee_privacy

- [50pts] Reddit: "How to avoid sensitive data/PII being part of LLM training" (r/LocalLLaMA) → 实操共识: 训练/推理前先脱敏（regex/spaCy/Presidio/Protegrity 开源版）; 8项清单含联邦学习、redaction、RBAC+审计日志、GDPR/CCPA/HIPAA 合规。→ 对项目价值: PII 清洗工具链选型参考, 可纳入本地 RAG 管道设计模式。
  URL: https://www.reddit.com/r/LocalLLaMA/comments/18s1lvj/how_to_avoid_sensitive_datapii_being_part_of_llm

- [50pts] Reddit: "Prompt injection is killing our self-hosted LLM deployment" (r/LocalLLaMA, 2026) → 自托管部署安全实战: 无100%水密的 prompt injection 防线（LLM 把一切当文本）; 关键最佳实践=MCP 工具层强制用户鉴权（AI 不能自行获取 token）、端到端访问控制评估、FMEA。→ 对项目价值: 企业自托管方案的安全架构章节必须包含 prompt injection 纵深防御, 直接支撑 confidential computing 交付物。
  URL: https://www.reddit.com/r/LocalLLaMA/comments/1qyljr0/prompt_injection_is_killing_our_selfhosted_llm

- [45pts] Reddit: "How do large companies securely integrate LLMs" (r/LocalLLaMA) → 企业集成 LLM 的最大路障=数据机密性（ERP/内部系统接入）。→ 对项目价值: 佐证 confidential/on-prem 部署的企业需求真实存在。
  URL: https://www.reddit.com/r/LocalLLaMA/comments/1oqrn1f/how_do_large_companies_securely_integrate_llms

- [40pts] Reddit: "Privacy Concerns with LLM Models (and DeepSeek)" (r/LocalLLaMA) → 云模型（含DeepSeek）隐私担忧持续, 驱动本地化迁移讨论。→ 对项目价值: 出海客户"数据不出境"卖点的海外叙事素材。
  URL: https://www.reddit.com/r/LocalLLaMA/comments/1i1ugj5/privacy_concerns_with_llm_models_and_deepseek_in

## 监管趋势判断

数据出境制度闭环（认证落地+行业指引细化），执法重心转向训练语料与开源模型供应链，本地化部署获监管侧论据。

---

## 本期最有价值发现

**"清朗·整治AI应用乱象"专项行动将"开源模型安全管理不到位"列为国家级执法重点（2026-04-30, CAC）** — 开源社区无身份认证、数据集/模型无审核清理机制被点名整治, 叠加训练语料合规与 AI 数据投毒, 意味着本地大模型部署客户（本项目核心受众）的开源模型来源治理已从技术问题升级为监管合规问题。直接支撑 AI 影响评估与供应商审查清单的更新: 开源模型供应链合规应成为必备审查项, 也是 confidential computing / 本地化部署价值主张的监管侧论据。次优: 《汽车数据出境安全指引(2026版)》提供行业细则模板, 汽车/制造客户出境路径可直接复用。
