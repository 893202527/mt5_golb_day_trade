CREATE TABLE IF NOT EXISTS ohlc (
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

CREATE TABLE IF NOT EXISTS signals (
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

CREATE TABLE IF NOT EXISTS trades (
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

CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_tf_time ON ohlc(symbol, timeframe, bar_time);
CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
