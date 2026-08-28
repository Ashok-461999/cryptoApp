# CryptoSignalApp

Crypto futures signal app — **all liquid USDT perpetuals**, **strict stop loss** on every signal, and **auto leverage** (2x–10x by coin tier).

## Features

| Feature | Detail |
|---------|--------|
| Scan universe | All Binance USDT-M perps with $10M+ volume (100+ coins) |
| Signals | CAN TAKE only, max 15/day UTC, sorted by confidence → R:R → volume |
| Stop loss | HARD SL mandatory — no signal without `stop_loss_price` |
| Leverage | Auto 2x–10x by tier + ATR + liquidation safety (2× stop buffer) |
| Capital | **₹20,000 INR** (~\$289 USDT for margin math) · 1% risk = **₹200/trade** |
| Paper trading | ON by default |

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Flutter client

```bash
cd client
flutter pub get
flutter run -d windows --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /signals/active` | All current TAKE signals with SL, leverage, margin plan |
| `GET /crypto/watchlist` | Full scanned universe with tier + volume |
| `GET /health` | Health check |
| `WS /ws/signals` | Live signal push |

**Market data source:** [Binance Vision](https://data-api.binance.vision) (`/api/v3/klines`, `/ticker/price`, `/ticker/24hr`, `/depth`) — no API key. Futures perp list + funding still use `fapi.binance.com` (Vision has no `/fapi` endpoints).

### Example signal response

```json
{
  "signals": [{
    "symbol": "PEPEUSDT",
    "direction": "LONG",
    "leverage": 3,
    "stop_loss_price": 0.00001180,
    "strict_sl_rule": "Exit immediately if price touches or closes below ...",
    "margin_usdt": 21.12,
    "max_loss_usdt": 5.10,
    "target_profit_usdt": 6.80,
    "trade_plan": "LONG PEPE · Entry ... · STRICT SL ... · 3x"
  }],
  "total_scanned": 142,
  "take_count_today": 8,
  "take_cap_today": 15,
  "utc_date": "2026-08-26"
}
```

## Project structure

```
CryptoApp/
├── backend/
│   └── app/
│       ├── signals/
│       │   ├── position_sizing_crypto.py   # Leverage + margin + strict SL
│       │   ├── crypto_scanner.py             # All-coin scanner
│       │   └── setups.py                     # FVG, liquidity sweep, ORB, VWAP
│       ├── services/
│       │   ├── crypto_watchlist.py           # Dynamic universe
│       │   └── crypto_futures_client.py      # Binance Futures API
│       └── api/routes/
│           ├── signals.py                    # /signals/active
│           └── crypto.py                     # /crypto/watchlist
└── client/                                   # Flutter UI
```

## Safety rules (enforced)

- No TAKE without `stop_loss_price`
- SL from setup structure (swing, ORB, FVG edge)
- SL distance: 0.3%–2.5% majors, up to 5% meme
- Liquidation must be ≥ 2× stop distance away
- Funding > 0.1% per 8h → skip signal
- Max 35% capital deploy per trade

## Tests

```bash
cd backend
pytest tests/ -v
```
