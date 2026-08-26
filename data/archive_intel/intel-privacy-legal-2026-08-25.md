# 情报简报: privacy-legal

**时间**: 2026-08-25
**源**: CAC官网(正文已抓取验证)/中文新闻/Reddit r/LocalLLaMA

## 高相关度发现

- [10pts] **数据出境安全管理政策法规问答（2026年7月）** — 网信办官方口径三连击：①出境告知+单独同意边界（"一揽子授权"无效，参考GB/T 42574-2023；第13条2-7项情形可豁免同意但**告知不可豁免**）；②安全评估结果延期6条件（目的/主体不变、3年量增幅≤20%、无重大安全事件，延期3年）；③招聘场景简历出境必要性判定（境外总部不参与录用决策=不具备必要性）。→ 直接可写入数据出境合规审查清单与DSAR/告知同意模板。来源: https://www.cac.gov.cn/2026-07/24/c_1786638883119336.htm
- [9pts] **《大型网络平台个人信息保护规定（征求意见稿）》**（网信办+公安部，2025-11-22，意见截止2025-12-22）— 认定门槛（注册5000万/月活1000万）、个保负责人须中国国籍且管理层任职并具否决权、重大泄露（100万人/10万敏感）触发强制第三方合规审计、第三方数据中心须报送基本信息。→ 供应商审查与平台客户尽调的新增义务点，建议跟踪正式稿出台。来源: https://www.cac.gov.cn/2025-11/22/c_1765543463511624.htm
- [8pts] **"清朗·整治AI应用乱象"专项行动**（2026-04-30部署，为期4个月）— 第一阶段7类问题含：大模型训练语料安全（未经授权数据训练）、AI数据投毒、开源模型安全管理不到位（开源社区数据集/模型代码审核与应急处置）、智能体窃取用户数据。→ 本地大模型部署项目的训练语料来源合规审查+开源模型供应链审查有了直接执法依据。来源: https://www.cac.gov.cn/2026-04/30/c_1779289298718765.htm
- [8pts] **Reddit: CloakLLM — 本地Ollama检测PII后再进云端LLM** — 开源PII脱敏中间件：regex+spaCy NER+本地Ollama三层检测（可抓地址/医疗/财务等上下文型PII），SHA-256哈希链审计日志（篡改即断链），宣称面向EU AI Act 2026-08合规。→ 印证"本地推理+脱敏代理"商业化窗口，与合规骨架产品定位吻合。来源: https://www.reddit.com/r/LocalLLaMA/comments/1rjodma/
- [7pts] **2026年个人信息保护系列专项行动阶段性成效**（网信中国，2026-08-19）— 累计核查2万余款App/SDK，督促4000余款整改，公开通报1100余款，下架处置400余款。→ 执法常态化证据，客户侧合规紧迫性素材。来源: https://www.secrss.com/articles/74212
- [7pts] **数据出境安全评估285个项目、超九成通过**（网信办发布会）— 《促进和规范数据跨境流动规定》实施后申报量降60%、标准合同备案降50%；评估平均<30工作日（法定45）；京津自贸区负面清单已备案实施，京沪深杭设数据出境服务中心。→ 出境便利化与强执法并行，AI出海客户路径清晰。来源: https://www.secrss.com/articles/74212

## 中相关度

- [6pts] **Reddit: LLM-Shield/PasteGuard** — OpenAI兼容隐私代理，Mask（脱敏后送云端+回填原文）或Route（含PII请求转本地Ollama）双模式，Presidio驱动24语言，数小时100+ GitHub星。来源: https://www.reddit.com/r/LocalLLaMA/comments/1q7bei7/
- [6pts] **Reddit: rehydra** — 可逆PII匿名化（round-trip），regex+XLM-RoBERTa NER，TS实现面向Electron/Edge层。来源: https://www.reddit.com/r/LocalLLaMA/comments/1q5iaml/
- [5pts] **Reddit: Qwen3.5 拒绝处理PII文件** — 本地部署下模型安全对齐过严，连"假数据"格式化任务都拒绝 → 本地LLM处理真实PII的场景存在对齐阻碍，需脱敏/沙箱方案兜底。来源: https://www.reddit.com/r/LocalLLaMA/comments/1s2gkfx/
- [5pts] **Reddit: 本地LLM隐私保障的质疑帖**（"Do not use local LLMs to privatize your data"）— 社区对本地推理=隐私安全的朴素等式提出反证（软件供应链信任问题）。→ 客户教育材料需覆盖供应链信任维度。来源: https://www.reddit.com/r/LocalLLaMA/comments/1ovzfui/
- [4pts] **金杜/锦天城解读《个人信息出境认证办法》** — 三路径（安全评估/标准合同/认证）制度全面落地，数据出境监管体系"3法+1条例+4规章"完备。来源: https://www.kingandwood.com/cn/zh/insights/latest-thinking/china-s-cross-border-data-transfer-supervision-system-and-the-measures-for-certification-of-personal-information-export.html
- [3pts] **《汽车数据出境安全指引（2026版）》** — 八部门联合印发，细化重要数据判定+安全漏洞/OTA类豁免申报，申报不要求提交原始数据。→ 行业化出境指引趋势样本。来源: https://policy.mofcom.gov.cn/claw/policyInfo.shtml?id=8728

## 监管趋势判断

出境路径便利化(认证办法落地/负面清单/评估提速)，AI训练语料与平台个保执法显著加码。

---

## 本期最有价值发现

**《数据出境安全管理政策法规问答（2026年7月）》**（CAC官网，2026-07-24）：网信办以问答形式给出三个实务裁决口径——出境单独同意必须独立交互且不得捆绑、同意可豁免但**告知义务永不可豁免**、招聘简历出境以"境外方是否参与录用决策"判定必要性。这是官方对长期实务争议（同意豁免边界）的首次明确表态，可直接固化为项目数据出境审查清单的新增检查项，也是向企业客户交付的现成合规依据。
