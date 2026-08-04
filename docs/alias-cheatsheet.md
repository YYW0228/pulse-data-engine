# VPS 快捷进入字母速查表 (Alias Cheatsheet)

> 更新: 2026-08-04 | Shell: zsh (主) + bash (同步)
> 配置: ~/.zshrc + ~/.bash_aliases
> 用法: 终端直接输入字母/命令即跳转

---

## 一、项目快捷字母 (cd 直达)

| 字母 | 命令 | 目标 |
|------|------|------|
| `se` | cd ~/projects/startalent-enterprise | 主产品 (企业AI培训) |
| `pe` | cd /root/projects/pulse-data-engine | 数据引擎 |
| `jc` / `j` | cd ~/projects/job-scraper | 招聘采集 (j 带 venv) |
| `hb` | cd ~/projects/hermes-brain | 藏识 (技能/记忆/配置) |
| `cag` / `l` | cd ~/projects/china-ai-governance | AI 治理法规库 |
| `ss` | cd ~/projects/SOVEREIGN-SINGULARITY | 主权单数 |
| `mib` | cd ~/projects/my-intelligence-base | 智能基础 |
| `ez` | cd ~/projects/ENTROPY-ZERO | 熵零 |
| `tp` | cd ~/projects/startalent-project-template | 项目模板 |

## 二、harness-devour 吞噬体系 (2026-08-04 新增) 🔥

| 字母 | 命令 | 目标 |
|------|------|------|
| `hd` | cd /root/harness-lab/repo | 吞噬私有仓库 (skill/评分卡/雷达/模式库) |
| `hdl` | cd /root/harness-lab | 吞噬工作区 (clone + 分析文档) |
| `hdscan` | 雷达扫描 | 白名单仓库 → 匹配度排序推荐 |
| `hdscore` | 评分门禁 | CI 吞噬评分 (<60 拦截) |
| `hdpat` | 模式库列表 | 已入库模式 (migrated/experiment/watch) |
| `hdskill` | cd repo/skill | 吞噬方法论 skill |

### 吞噬工作流 (一字母直达)
```
hd           → 进吞噬仓库
hdscan       → 雷达扫描 (找下一个吞噬目标)
hdscore      → 评分 (质量门禁)
hdpat        → 模式库 (已吸收模式)
```

## 三、tmux 会话入口 (go 前缀)

| 字母 | 命令 | 目标 |
|------|------|------|
| `gope` | tmux pe | Pulse Data Engine |
| `gose` | tmux se | StarTalent |
| `golegal` / `gocag` | tmux legal | china-ai-governance |
| `gojob` | tmux jobs + venv | job-scraper |
| `gosovereign` | tmux sovereign | SOVEREIGN-SINGULARITY |
| `gohermes` | tmux hermes | ~/projects 根 |
| `tmux-pulse` | tmux pulse | Pulse (bash 侧) |
| `tmux-se` | tmux se | StarTalent (bash 侧) |
| `tls` / `tl` | tmux ls | 列出会话 |
| `tk` | tmux kill-session -t | 杀会话 |

## 四、git 快餐

| 字母 | 命令 |
|------|------|
| `gs` | git status -sb |
| `gl` | git log --oneline --graph --all -20 |
| `gd` / `gds` / `gdc` | git diff (工作区/暂存/缓存) |
| `gp` / `gpl` | git pull --rebase / git pull |
| `gc` | git commit -m |
| `gca` | git commit --amend --no-edit |
| `gco` / `gcb` | git checkout / -b |
| `gb` / `gr` | git branch -a / remote -v |
| `gst` / `gstp` | git stash / stash pop |
| `gpu` | git push |

## 五、查找 & 资源

| 字母 | 命令 |
|------|------|
| `fd` | find . -type f -name |
| `rg` | grep -rn --color |
| `du1` / `dud` | du -sh 各目录 (排序) |
| `psa` | ps auxf |
| `mem` / `cpu` | 内存/CPU Top20 |
| `ports` | ss -tulanp (端口) |
| `dfh` | df -h (磁盘) |
| `hlogs` | hermes logs |

## 六、导航

| 字母 | 命令 |
|------|------|
| `go` | cd ~/projects + ls |
| `golog` | cd ~/projects/logs |
| `gobak` | cd ~/projects/backups |
| `lt` / `lh` | 按时间/大小排序 ls |

---

*记忆口诀: se/pe/jc = 三主力 | hb/cag = 两知识库 | hd = 吞噬引擎*
