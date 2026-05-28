# Obsidian + Claude 集成设计

## 目标

搭建 Obsidian Vault + Claude Code + Text Generator 插件三者协作环境，覆盖日常笔记、量化交易研究、通用知识管理三个场景。

## Vault 结构

```
C:\Users\89320\Documents\TradingVault/
├── 00-Daily/              # 每日笔记
├── 10-Trading/            # 量化交易研究日志
│   ├── strategies/        # 策略记录
│   ├── backtest/          # 回测笔记
│   └── journal/           # 交易日志
├── 20-Knowledge/          # 通用知识管理
├── 30-AI-Chats/           # AI 对话记录
├── templates/             # 模板文件
├── attachments/           # 图片、附件
├── .obsidian/             # Obsidian 配置
├── .gitignore
└── CLAUDE.md
```

Vault 目录同时作为 Claude Code 项目目录。

## 组件

### 1. Obsidian + Text Generator 插件

- 配置两个 API Profile：Claude (Anthropic) 和 DeepSeek
- Claude Profile：通过代理/中转访问 Anthropic API
- DeepSeek Profile：OpenAI 兼容接口直连
- 统一模板：根据场景切换模型时使用对应的 prompt 模板

### 2. Claude Code 操作 Vault

- `CLAUDE.md` 定义行为边界：
  - 允许：新建文件、编辑文件内容、搜索笔记
  - 禁止：重命名/移动已有文件（防止 [[wiki-link]] 死链）
  - 编辑规则：保留 frontmatter、使用 [[wiki-link]] 语法
- Vault 目录启动 Claude Code 即可操作所有笔记

### 3. Git 版本控制

- `git init` 初始化
- `.gitignore` 排除 `workspace.json` 等频繁变动的 Obsidian 配置
- 所有笔记修改可追溯、可回滚

## 实施步骤

1. 安装 Obsidian（确认已安装）
2. 创建 Vault 目录及结构
3. 安装并配置 Text Generator 插件
4. 编写 CLAUDE.md
5. Git 初始化
6. 创建常用模板（日记模板、交易日志模板）

## 不做

- 不装过多插件，初始只装 Text Generator + Tag Wrangler
- 不做自动链接管理，由 Obsidian 自身处理
- 不做多设备同步，保持本地单机
