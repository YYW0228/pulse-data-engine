# 密钥保险单 (Secret Vault Manifest)

> 用途: VPS 崩溃/到期后的密钥恢复清单 (P1-11)
> ⚠️ 本文件不含真实密钥值! 值是敏感数据, 只存密码管理器 (LastPass/1Password/加密笔记)
> 使用方法: 按表逐项把"值"填入你的密码管理器, 然后本文件标记 [已备份]

---

## 一、密钥清单

| # | 密钥名 | 用途 | 存储位置 | 密码管理器 | 恢复步骤 |
|---|--------|------|---------|-----------|---------|
| 1 | DEEPSEEK_API_KEY | 问答/评审/洞察 LLM | ~/.hermes/.env | [ ] | 重建手册第4步 |
| 2 | TELEGRAM_BOT_TOKEN | Telegram 桥 | ~/.hermes/.env | [ ] | 重建手册第4步 |
| 3 | CF_API_TOKEN | Cloudflare (R2/Worker) | ~/.hermes/.env | [ ] | 重建手册第4步 |
| 4 | TERMINAL_SSH_KEY | VPS SSH | ~/.hermes/.env + ~/.ssh/ | [ ] | ssh-keygen 或恢复 |
| 5 | FIRECRAWL_API_KEY | job-scraper 采集 | GitHub Actions secret | [ ] | gh secret set |
| 6 | FIRECRAWL_KEY2 | job-scraper 备用 | GitHub Actions secret | [ ] | gh secret set |
| 7 | TAVILY_API_KEY | job-scraper 搜索 | GitHub Actions secret | [ ] | gh secret set |
| 8 | GH_TOKEN / SSH key | git push | ~/.ssh/ + gh auth | [ ] | gh auth login |
| 9 | BROWSERBASE_PROXIES | 浏览器代理 | ~/.hermes/.env | [ ] | 重建手册第4步 |
| 10 | TELEGRAM_ALLOWED_USERS | Telegram 白名单 | ~/.hermes/.env | [ ] | 重建手册第4步 |

## 二、备份位置 (值存哪)

```
首选: 密码管理器 (1Password/LastPass/Bitwarden) — 新建条目 "StarTalent VPS 密钥"
  条目字段: 上述 10 项 key: value
备选: 加密笔记 (Obsidian 加密 vault / 本地加密文件)
  文件: ~/secure/vps-secrets.gpg (gpg --symmetric 加密)
  口令: 单独记录 (不与其他密钥同存)
```

## 三、恢复步骤 (新机器)

```bash
# 1. 从密码管理器取出全部 10 项
# 2. 写入 ~/.hermes/.env
cat > ~/.hermes/.env << 'EOF'
DEEPSEEK_API_KEY=<从密码管理器>
TELEGRAM_BOT_TOKEN=<从密码管理器>
# ... 全部 10 项
EOF
chmod 600 ~/.hermes/.env

# 3. GitHub secrets (job-scraper CI 用)
gh secret set FIRECRAWL_API_KEY --repo YYW0228/job-scraper
gh secret set TAVILY_API_KEY --repo YYW0228/job-scraper
# 4. git auth
gh auth login
```

## 四、安全规则

1. 本清单文件可进 git (无值), 但 .env 永不进 git
2. 每季度检查一次密钥有效性 (密码轮换)
3. 密钥泄露时: 立即在对应平台撤销 + 更新密码管理器 + 通知相关人员

## 五、当前备份状态 (待办)

```
[ ] 1. 已把 10 项值填入密码管理器 (手动操作, 需你在密码管理器操作)
[ ] 2. 已标记本清单 [已备份]
[ ] 3. 已用 gpg 加密一份副本放 ~/secure/
```

> 这是整个备份体系的唯一单点 — 完成它, VPS 才是真正"不丢"
