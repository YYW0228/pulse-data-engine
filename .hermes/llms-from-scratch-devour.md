# 吞噬评估: rasbt/LLMs-from-scratch (2026-08-12)

> 来源: 白云 Telegram 链接 → 已 clone 至 `/Users/mac/projects/LLMs-from-scratch` (depth 1, 11M)
> 类型: **学习型资产** (非 harness 组件) — 不移植进任何产品, 作为认知/教学资产使用

## 一、仓库概况
- 《Build a Large Language Model (From Scratch)》官方代码 (Sebastian Raschka, Manning)
- 规模: 149 py / 33,462 行 / 8 章 + appendix A-E
- 主线: ch01 数据准备 → ch02 注意力 → ch03 GPT 实现 → ch04 预训练 → ch05 预训练实战 → ch06 微调 → ch07 指令微调
- 亮点目录: ch07 `gpt_to_llama` (GPT→Llama 架构迁移), ch11 qwen3 / ch12 gemma3 权重加载, ch08 内存高效权重加载
- 依赖重 (torch/tensorflow), 仅本地学习用, 不进任何 venv

## 二、价值评估 (对当前主线)

| 价值维度 | 评分 | 说明 |
|---------|------|------|
| AI 落地 harness 商业交付 | ★★★☆☆ | 向客户解释 LLM 机制的权威教材; ch07 gpt_to_llama 可支撑"换模型少改"叙事 (Harness 第一性原理: 模型变强时架构应变简单) |
| 白云复习 Python/LLM 底层 | ★★★★★ | 主线就是逐步从零实现, 与"读源码复习编程"完全对齐; ch01-03 是绝佳复习素材 |
| 可借鉴模式 (本地部署) | ★★★☆☆ | ch11/qwen3 + ch12/gemma3 的权重加载/架构解析, 对本地模型部署 (Qwen2.5-32B 基座) 有参考 |
| 直接可复用组件 | ★☆☆☆☆ | 教学代码, 无产品级封装; 不满足吞噬"Python 重写集成"标准 |

## 三、决策
1. **保留** `/Users/mac/projects/LLMs-from-scratch` 为本地学习资产 (不删除)
2. **不移植** 任何代码到 pulse/hermes-brain (与吞噬铁律一致: 只吸收高价值模式, 不为了吞噬而吞噬)
3. **推荐学习路径** (白云, 每次 30-60 分钟):
   - ch01 (tokenizer/BPE) → ch02 (注意力机制) → ch03 (GPT 骨架) → ch04 (预训练循环)
   - 有余力: ch07 gpt_to_llama (理解架构迁移 = harness 换模型层设计)
4. **可沉淀知识**: 若后续做"AI 落地 harness"售前, 用 ch02/ch03 的图示向客户讲清"LLM 不是黑盒" — 这是差异化信任素材

## 四、状态
- [x] clone + 结构评估
- [x] 吞噬决策记录
- [ ] 白云按学习路径推进 (可选, 用户侧)
