# MT5 EA + GitHub + AI 黄金量化交易系统

## 目标

搭建全自动 XAUUSD 量化交易系统：MT5 EA 执行交易 + Python AI 生成信号，通过 ZeroMQ 实时通信，PostgreSQL 存储数据，GitHub 版本管理。

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                     Windows (本地)                        │
│                                                          │
│  ┌──────────┐    ZeroMQ     ┌──────────────────┐        │
│  │  MT5 EA  │ ◄──────────► │  Python AI 服务   │        │
│  │  (MQL5)  │   PUB/REQ    │  (本地进程)        │        │
│  └────┬─────┘               └────┬─────────────┘        │
│       │ 行情读取                  │                       │
│       ▼                          ▼                       │
│  ┌──────────┐              ┌──────────────┐             │
│  │  MT5     │              │  PostgreSQL   │             │
│  │  数据源   │              │  (行情+日志)   │             │
│  └──────────┘              └──────┬────────┘             │
│                                   │                       │
│                          ┌────────▼────────┐             │
│                          │  LLM API 调用    │             │
│                          │  (DeepSeek/Claude)│            │
│                          └─────────────────┘             │
└─────────────────────────────────────────────────────────┘
```

**核心链路：**
- EA 每根 M5 K 线闭合 → ZeroMQ PUB 推送 OHLC → Python 接收
- Python 特征计算 → ML 推理 → LLM 确认 → ZeroMQ REP 返回信号
- EA 执行下单（市价单 + 止损止盈）
- PostgreSQL 存行情 + 信号 + 成交，用于回测和模型训练
- 初期同机部署 Windows，后期可迁 Python 到云端

## 通信协议 (ZeroMQ)

### 行情通道 (PUB/SUB)

EA → Python，主题 `OHLC`：

```json
{
  "type": "ohlc",
  "symbol": "XAUUSD",
  "tf": "M5",
  "time": "2026-05-28T10:00:00",
  "open": 2650.12,
  "high": 2652.30,
  "low": 2649.80,
  "close": 2651.45,
  "tick_volume": 3240,
  "spread": 28
}
```

### 信号通道 (REQ/REP)

EA → Python，请求信号：

```json
{"type": "query", "symbol": "XAUUSD", "tf": "M5"}
```

Python → EA，返回信号：

```json
{
  "action": "buy",
  "confidence": 0.72,
  "entry_price": 2651.45,
  "sl": 2648.00,
  "tp": 2658.00,
  "reason": "LLM确认：上升趋势中突破2650阻力"
}
```

**交互节奏：**
- M5 闭合 → PUB 行情 + REQ 信号查询
- H1/H4 闭合 → 仅 PUB 行情（大周期特征），不查询信号
- 入场信号仅在 M5 收盘触发

## 数据库 (PostgreSQL)

```sql
CREATE TABLE ohlc (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    bar_time TIMESTAMPTZ NOT NULL,
    open DECIMAL(10,2) NOT NULL,
    high DECIMAL(10,2) NOT NULL,
    low DECIMAL(10,2) NOT NULL,
    close DECIMAL(10,2) NOT NULL,
    tick_volume INT NOT NULL DEFAULT 0,
    spread INT NOT NULL DEFAULT 0,
    UNIQUE(symbol, timeframe, bar_time)
);

CREATE TABLE signals (
    id BIGSERIAL PRIMARY KEY,
    bar_time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    action VARCHAR(10) NOT NULL,
    confidence DECIMAL(4,3) NOT NULL,
    entry_price DECIMAL(10,2),
    sl DECIMAL(10,2),
    tp DECIMAL(10,2),
    ml_model VARCHAR(50),
    llm_response TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES signals(id),
    ticket BIGINT,
    symbol VARCHAR(10) NOT NULL,
    direction VARCHAR(5) NOT NULL,
    volume DECIMAL(5,2) NOT NULL,
    entry_price DECIMAL(10,2) NOT NULL,
    exit_price DECIMAL(10,2),
    sl DECIMAL(10,2),
    tp DECIMAL(10,2),
    profit DECIMAL(10,2),
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    status VARCHAR(10) DEFAULT 'open'
);

CREATE INDEX idx_ohlc_symbol_tf_time ON ohlc(symbol, timeframe, bar_time);
CREATE INDEX idx_signals_time ON signals(created_at DESC);
CREATE INDEX idx_trades_status ON trades(status);
```

## AI 策略管线

```
M5 K线闭合
    │
    ▼
┌─────────────────────────┐
│ 特征工程 (FeatureGen)     │
│ - 过去N根K线的OHLCV       │
│ - 技术指标 (RSI/EMA/MACD) │
│ - H1/H4 大周期趋势标签    │
│ - 订单流特征 (spread/量)  │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ ML 模型 (XGBoost)        │
│ - 二分类: buy/sell/hold  │
│ - 置信度阈值: > 0.6      │
└──────────┬──────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
   否            是
   hold      ┌─────────────────────┐
             │ LLM 确认 (LLM Gate) │
             │ - 盘面摘要 + ML信号  │
             │ - 返回 AGREE/REJECT │
             └──────────┬──────────┘
                        │
                  ┌─────┴─────┐
                同意         否决
                  │           │
              最终信号       hold
```

**LLM Prompt 模板：**
```
你是黄金(XAUUSD)交易顾问。当前M5时间框架。

盘面数据：
- 价格: {close}，涨跌幅: {change}%
- 大周期方向: H1={h1_trend}, H4={h4_trend}
- 技术指标: RSI={rsi}, EMA20={ema20}, 布林带位置={bb_pos}

ML模型信号: {action}，置信度: {confidence}

请判断是否同意该信号。只回复 AGREE 或 REJECT，并给一句话理由。
```

## 项目文件结构

```
mt5_golb_day_trade/
├── ea/                          # MT5 EA 源码
│   ├── Experts/
│   │   └── GoldenBot.mq5        # 主EA
│   ├── Include/
│   │   ├── ZmqChannel.mqh       # ZeroMQ 通道封装
│   │   └── OrderManager.mqh     # 下单/止损/止盈管理
│   └── Libraries/
│       └── zmq/                 # ZeroMQ MQL5 binding
│
├── ai/                          # Python AI 服务
│   ├── server.py                # ZeroMQ 服务主进程
│   ├── feature_engine.py        # 特征工程
│   ├── ml_model.py              # XGBoost 模型训练/推理
│   ├── llm_gate.py              # LLM API 调用
│   ├── db.py                    # PostgreSQL 读写
│   ├── config.py                # 配置
│   └── requirements.txt
│
├── data/                        # 训练数据和模型
│   ├── models/
│   └── features/
│
├── scripts/                     # 工具
│   ├── backtest.py
│   ├── train.py
│   └── init_db.sql
│
├── docs/
│   └── superpowers/
│       ├── specs/
│       └── plans/
│
├── .gitignore
└── README.md
```

## 备选方案（记录）

- **方案 B（纯 MQL5 + API）**：全部在 EA 内实现，策略简单但依赖 LLM API，延迟和稳定性风险。适合轻量场景。
- **方案 C（混合 Redis + 微服务）**：生产级架构，EA → Redis Stream → Python Worker。后期规模化可选。

## 不做

- 不做高频/剥头皮策略，专注 M5 及以上周期
- 不在 MQL5 内实现复杂 ML
- 不在此阶段支持多品种（仅 XAUUSD）
- 不在此阶段做云端部署
