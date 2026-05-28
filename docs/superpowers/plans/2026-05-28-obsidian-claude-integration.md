# Obsidian + Claude 集成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 Obsidian Vault + Claude Code + Text Generator 插件协作环境

**Architecture:** 本地 Obsidian Vault 位于 `~/Documents/TradingVault/`，同时作为 Claude Code 项目目录。Obsidian 端通过 Text Generator 插件双 Profile 切换 Claude/DeepSeek 模型。Claude Code 通过 CLAUDE.md 定义行为边界直接操作 Markdown 笔记。

**Tech Stack:** Obsidian, Text Generator plugin, Tag Wrangler plugin, Git

---

### Task 1: 确认 Obsidian 安装并创建 Vault

**Files:**
- Create: `C:\Users\89320\Documents\TradingVault\` (directory tree)

- [ ] **Step 1: 验证 Obsidian 安装路径**

```bash
ls "C:\Users\89320\AppData\Local\obsidian" 2>/dev/null && echo "FOUND" || ls "C:\Users\89320\AppData\Local\Obsidian" 2>/dev/null && echo "FOUND" || echo "NOT FOUND — will check other paths"
```

- [ ] **Step 2: 若未找到，搜索 Obsidian 可执行文件**

```bash
ls "C:\Users\89320\AppData\Local\Programs\obsidian" 2>/dev/null || ls "C:\Program Files\obsidian" 2>/dev/null || echo "Searching..."; find /c/Users/89320 -maxdepth 4 -name "Obsidian.exe" -type f 2>/dev/null | head -5
```

- [ ] **Step 3: 创建 Vault 目录结构**

```bash
VAULT="C:/Users/89320/Documents/TradingVault"
mkdir -p "$VAULT/00-Daily"
mkdir -p "$VAULT/10-Trading/strategies"
mkdir -p "$VAULT/10-Trading/backtest"
mkdir -p "$VAULT/10-Trading/journal"
mkdir -p "$VAULT/20-Knowledge"
mkdir -p "$VAULT/30-AI-Chats"
mkdir -p "$VAULT/templates"
mkdir -p "$VAULT/attachments"
```

- [ ] **Step 4: 验证目录结构**

```bash
find "C:/Users/89320/Documents/TradingVault" -type d | sort
```

Expected: 11 directories listed

---

### Task 2: Git 初始化 + .gitignore

**Files:**
- Create: `C:\Users\89320\Documents\TradingVault\.gitignore`
- Create: `C:\Users\89320\Documents\TradingVault\.git` (via git init)

- [ ] **Step 1: 初始化 Git 仓库**

```bash
cd "C:/Users/89320/Documents/TradingVault" && git init
```

Expected: `Initialized empty Git repository in ...`

- [ ] **Step 2: 写入 .gitignore**

Write file `C:\Users\89320\Documents\TradingVault\.gitignore`:

```
# Obsidian workspace — changes every time you switch panes
.obsidian/workspace.json
.obsidian/workspace-mobile.json

# Obsidian cache
.obsidian/cache

# System files
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.bak
```

- [ ] **Step 3: 首次提交**

```bash
cd "C:/Users/89320/Documents/TradingVault" && git add .gitignore && git add . && git commit -m "init: TradingVault with directory structure"
```

---

### Task 3: 编写 CLAUDE.md

**Files:**
- Create: `C:\Users\89320\Documents\TradingVault\CLAUDE.md`

Write file `C:\Users\89320\Documents\TradingVault\CLAUDE.md`:

```markdown
# TradingVault

This is an Obsidian vault for daily notes, trading research, and knowledge management.
Claude Code operates on this vault directly.

## File conventions

- All notes use Obsidian-flavored markdown with YAML frontmatter
- Internal links use `[[wiki-link]]` syntax
- File names: `YYYY-MM-DD.md` for daily notes, kebab-case for others
- Attachments go in `attachments/`

## Behavior rules

- ALLOWED: create new files, edit file content, search notes with Grep/Glob
- FORBIDDEN: rename or move existing files (breaks [[wiki-link]] references)
- When editing existing notes, preserve their frontmatter block
- When creating new notes, add appropriate frontmatter based on the template in `templates/`

## Directory map

| Directory | Purpose |
|-----------|---------|
| `00-Daily/` | Daily notes |
| `10-Trading/strategies/` | Strategy docs |
| `10-Trading/backtest/` | Backtest notes |
| `10-Trading/journal/` | Trade journal |
| `20-Knowledge/` | General knowledge |
| `30-AI-Chats/` | AI conversation logs |
| `templates/` | Note templates |
```

- [ ] **Step: 提交 CLAUDE.md**

```bash
cd "C:/Users/89320/Documents/TradingVault" && git add CLAUDE.md && git commit -m "add CLAUDE.md with vault behavior rules"
```

---

### Task 4: 创建笔记模板

**Files:**
- Create: `C:\Users\89320\Documents\TradingVault\templates\daily-note.md`
- Create: `C:\Users\89320\Documents\TradingVault\templates\trade-journal.md`

- [ ] **Step 1: 创建每日日记模板**

Write file `C:\Users\89320\Documents\TradingVault\templates\daily-note.md`:

```markdown
---
date: {{date}}
tags: [daily]
---

# {{date}}

## 今日目标

- [ ] 

## 交易笔记

[[10-Trading/journal/{{date}}]]

## 随记

## 总结
```

- [ ] **Step 2: 创建交易日志模板**

Write file `C:\Users\89320\Documents\TradingVault\templates\trade-journal.md`:

```markdown
---
date: {{date}}
tags: [trading, journal]
---

# 交易日志 {{date}}

## 持仓

| 品种 | 方向 | 手数 | 开仓价 | 止损 | 止盈 |
|------|------|------|--------|------|------|

## 今日操作

| 时间 | 品种 | 操作 | 价格 | 手数 | 盈亏 |
|------|------|------|------|------|------|

## 复盘

## 明日计划
```

- [ ] **Step 3: 提交模板**

```bash
cd "C:/Users/89320/Documents/TradingVault" && git add templates/ && git commit -m "add daily note and trade journal templates"
```

---

### Task 5: 打开 Obsidian 并加载 Vault

- [ ] **Step 1: 启动 Obsidian 并打开 Vault**

找到 Obsidian.exe 的路径（Task 1 步骤 2 的结果），然后打开该 Vault 文件夹作为 Obsidian Vault。

这需要在 Obsidian GUI 中操作：点击 "Open folder as vault" → 选择 `C:\Users\89320\Documents\TradingVault`

> **无法自动化的步骤**：Obsidian GUI 操作需用户手动完成。

- [ ] **Step 2: 确认 Vault 加载成功**

打开 Obsidian 后，确认侧边栏显示目录结构：00-Daily, 10-Trading, 20-Knowledge, 30-AI-Chats, templates.

---

### Task 6: 安装并配置 Text Generator 插件

> **以下步骤在 Obsidian GUI 中操作**

- [ ] **Step 1: 关闭安全模式**

Settings → Community Plugins → Turn off "Restricted mode"

- [ ] **Step 2: 安装 Text Generator**

Settings → Community Plugins → Browse → 搜索 "Text Generator" → Install → Enable

- [ ] **Step 3: 安装 Tag Wrangler**

Settings → Community Plugins → Browse → 搜索 "Tag Wrangler" → Install → Enable

- [ ] **Step 4: 配置 Claude Profile**

Text Generator 设置 → Profiles → 新建 Profile：

```
Name: Claude
API Type: Anthropic
Model: claude-sonnet-4-6
Base URL: <你的代理/中转地址>
API Key: <Anthropic API Key>
Max Tokens: 4096
Temperature: 0.7
```

- [ ] **Step 5: 配置 DeepSeek Profile**

Text Generator 设置 → Profiles → 新建 Profile：

```
Name: DeepSeek
API Type: OpenAI Compatible
Model: deepseek-chat
Base URL: https://api.deepseek.com/v1
API Key: <DeepSeek API Key>
Max Tokens: 4096
Temperature: 0.7
```

- [ ] **Step 6: 配置模板关联**

Text Generator 设置 → Templates：导入 `templates/` 目录下的模板，配置快捷键或命令触发。

---

### Task 7: 最终验证

- [ ] **Step 1: 测试 Claude Code 访问 Vault**

在 Vault 目录下启动 Claude Code：

```bash
cd "C:/Users/89320/Documents/TradingVault" && claude --print "列出 00-Daily 目录下有哪些文件"
```

Expected: 正常列出目录内容（当前应该为空，无误即可）

- [ ] **Step 2: 测试创建笔记**

```bash
cd "C:/Users/89320/Documents/TradingVault" && claude --print "帮我在 00-Daily/ 下创建今天的每日笔记 2026-05-28.md"
```

- [ ] **Step 3: 在 Obsidian 中测试 Text Generator**

打开任意笔记 → 选中空白区域 → 使用 Text Generator 命令生成文字（用 DeepSeek profile 测试，国内直连可验证）

- [ ] **Step 4: 最终 Git 提交**

```bash
cd "C:/Users/89320/Documents/TradingVault" && git status && git add -A && git commit -m "complete initial setup: templates, CLAUDE.md, Obsidian config"
```
