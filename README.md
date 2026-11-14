# btc-cent-forecast-01 — BTC 4-hour-ahead price forecast

Forecasts Bitcoin's price 240 minutes after each checkpoint, from the
preceding 72 hours of 1-minute closes (Coinbase Wrapped BTC / USDC Orca
pool price, as recorded by make.fun).

## Program

`main.py` (Python 3.13, stdlib only, no network, deterministic). Reads
`$MAKEFUN_INPUT_DIR` (default `/input`), writes `$MAKEFUN_OUTPUT_DIR`
(default `/output`); one `<id>.out` per `<id>.in`:

```json
{"forecasts": [{"case": "<id>", "price": <number>}]}
```

Run locally:

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## Method

All work is in log-price space; the forecast is the checkpoint close
(persistence) adjusted by a small, heavily shrunk drift:

1. **Momentum** — EWMA (half-life 30 min) of 1-minute log returns,
   extrapolated over the 240-minute horizon and damped by 0.20.
2. **Mean reversion** — `-0.08 * (log price - EWMA of log price,
   half-life 720 min)`, pulling the forecast toward the slow 12-hour level.
3. **Shrinkage** — total log drift clamped to ±0.004 (±0.4%), so the guess
   never strays far from persistence. Forecast = last close × exp(drift),
   rounded to 5 decimals.

Few parameters, strong shrinkage: 6 practice cases cannot support a
heavily tuned model.

## Validation (practice cases p00–p05)

- **Walk-forward pseudo-validation** — forecast the close at
  (checkpoint − 240 min + 240 min) using only data up to checkpoint − 240
  min, at 8 pseudo-checkpoints per case (48 targets total):
  **MAE 30,632 cents vs persistence 32,968 cents (−7.1%)**.
  Late checkpoints (closest to the real ones): −12.4%; early ones: −0.4%
  (neutral — the model does not hurt in a flat regime).
- **Coinbase BTC-USD closes as a proxy for the 6 real practice targets**
  (targets +240 min after each checkpoint):
  **MAE 39,467 cents vs persistence 45,904 cents (−14.0%)**.
  (Coinbase is a proxy; the scored actuals come from the Orca pool, and
  the house baseline on the pool is 44,522 cents.)

Local run: all 6 practice outputs parse with the exact required shape,
byte-identical across two runs, ~0.12 s total (limit is 8 s per case).
