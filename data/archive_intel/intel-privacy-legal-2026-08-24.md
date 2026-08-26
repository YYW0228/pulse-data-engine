# 情报简报: privacy-legal

**时间**: 2026-08-24 (cron 采集)
**源**: CAC官网(正文已验证) / 律所解读 / Reddit r/LocalLLaMA

## 高相关度发现

- [95pts] **《个人信息出境认证办法》落地施行, 数据出境三路径制度全面闭环** (国家网信办+市场监管总局令第20号, 2025-10-17公布, 2026-01-01施行; 适用: 非CIIO、累计出境10万-100万人个人信息或<1万敏感信息、不含重要数据; 禁止数量拆分规避安全评估) → 项目"数据出境"合规服务有了第三条法定路径, PIA/告知同意/认证申请成为可交付产品线
  - https://www.cac.gov.cn/2025-10/17/c_1762449728720008.htm
  - 解读: https://www.kingandwood.com/cn/zh/insights/latest-thinking/china-s-cross-border-data-transfer-supervision-system-and-the-measures-for-certification-of-personal-information-export.html

- [90pts] **数据出境安全评估首批结果2026年前后集中届满, 延期申请窗口收紧** (有效期3年, 届满前60个工作日内经省级网信办申请; 6项条件含20%出境量增幅量化红线、3年无重大安全事件; 不满足即转重新申报, 周期显著更长) → 企业合规刚需窗口期, 自评+台账+延期申报是2026下半年高价值服务点
  - https://www.allbrightlaw.com/CN/10475/8cd77534cc2487e1.aspx (2026-07解读)
  - https://www.jswx.gov.cn/shuju/zixun/202607/t20260724_1346737.shtml (2026-07问答转载)

- [85pts] **中央网信办"清朗·整治AI应用乱象"专项行动 (2026-04-30部署, 为期4个月)** — 第一阶段7类问题含: 大模型应备未备、训练语料安全(未经授权数据/来源合规)、AI数据投毒、生成标识落实、**开源模型安全管理不到位**(开源社区数据集/模型代码无审核与应急处置机制)、智能体窃取用户数据账户密钥 → 直接映射项目大模型备案+训练数据合规+开源模型治理评估三块业务
  - https://www.cac.gov.cn/2026-04/30/c_1779289298718765.htm (正文已验证)

- [80pts] **CAC 2026年1月《数据出境安全管理政策法规问答》** — 明确标准合同/认证与安全评估的衔接与爬坡规则 (累计出境超100万人或超1万敏感信息必须转申报安全评估, 且需将此前通过合同/认证出境量纳入申报范围); 粤港澳大湾区标准合同不得向区外提供个人信息 → 合规路径选择的判定规则可直接落成决策树工具
  - https://www.cac.gov.cn/2026-01/30/c_1771505108953002.htm (正文已验证)

## 中相关度

- [65pts] **Reddit r/LocalLLaMA: "How do large companies securely integrate LLMs"** — 企业用LLM做自主智能体对接内部系统(ERP/chat)的最大阻碍是数据保密性 (data confidentiality) → 佐证"本地部署+on-device推理"需求真实存在, 与项目本地大模型合规定位直接相关
  - https://www.reddit.com/r/LocalLLaMA/comments/1oqrn1f/

- [60pts] **Reddit r/LocalLLaMA: "Do not use local LLMs to privatize your data"** — 提醒用本地模型做数据脱敏/私有化处理的隐患 → 本地推理≠自动合规, 恰是项目"本地部署≠合规自动达成"叙事的海外镜像
  - https://www.reddit.com/r/LocalLLaMA/comments/1ovzfui/

- [55pts] **Reddit r/LocalLLaMA: "Are Local LLMs Truly Private? / does running locally actually protect you"** — 讨论"runs locally ≠ private": 日志/历史明文存储仍是暴露面, 隐私取决于推理软件与周边工具链 → 本地LLM隐私论证需覆盖数据落盘/日志/历史, 可作技术审查checklist输入
  - https://www.reddit.com/r/LocalLLaMA/comments/1idlz1x/ ; https://www.reddit.com/r/LocalLLaMA/comments/1qpj8q7/

- [55pts] **《汽车数据出境安全指引(2026版)》** (2026-02, 工信部等八部门) — 九类免于申报情形(含安全漏洞/事件/OTA源代码类重要数据, 需事先报告备案)、细化汽车重要数据判定规则、申报不要求提交原始数据 → 行业指引模式的样板, 可预期更多垂直行业指引跟进
  - https://policy.mofcom.gov.cn/claw/policyInfo.shtml?id=8728

- [50pts] **Reddit r/LocalLLaMA: DeepSeek 隐私担忧讨论** — DeepSeek等云模型的隐私顾虑持续, 驱动用户转向本地推理 → 与项目"数据不出域"卖点共振
  - https://www.reddit.com/r/LocalLLaMA/comments/1i1ugj5/

## 监管趋势判断

数据出境三路径闭环+评估届满续期高峰, 大模型备案与语料合规执法收紧, 本地部署需求上升。

## 最有价值发现

**数据出境安全评估首批结果2026年集中届满** — 2022-2023年首批过评企业将在2026年陆续到期, 延期需在届满前60个工作日窗口内申请且须满足20%增幅等6项条件, 不满足即转重新申报(周期更长)。这构成2026下半年确定性合规刚需: 企业必须做合规自检、出境台账、PIA更新。对项目即: 将"评估延期/重新申报"包装为可复用的合规服务包 (自检清单+台账模板+六条件核对+申报文书), 与本地大模型合规方案打包销售, 商业价值直接。
