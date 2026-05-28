# MT5 Gold Day Trade

Automated XAUUSD trading system: MT5 EA + Python AI signals via ZeroMQ.

## Structure

- `ea/` — MQL5 Expert Advisor source
- `ai/` — Python AI signal service
- `data/` — trained models and feature configs
- `scripts/` — training and backtest utilities

## Quick Start

1. `cd ai && pip install -r requirements.txt`
2. `python scripts/init_db.sql` (PostgreSQL)
3. `python ai/server.py`
4. Load `ea/Experts/GoldenBot.mq5` in MT5

## License

MIT
