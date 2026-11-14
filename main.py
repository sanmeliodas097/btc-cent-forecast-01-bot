#!/usr/bin/env python3
"""btc-cent-forecast-01 entry: forecast BTC's price 240 minutes ahead.

Method (log-price space, heavily shrunk toward persistence):
  * Momentum: EWMA (half-life 30 min) of 1-minute log returns, extrapolated
    over the 240-minute horizon and damped by 0.20.
  * Mean reversion: -0.08 * (log price - EWMA of log price, half-life 720 min),
    pulling the forecast back toward the slow 12-hour level.
  * Total log drift is clamped to +/-0.004 (+/-0.4%), so the guess never
    strays far from the checkpoint close (persistence).
  * Forecast = last close * exp(drift), rounded to 5 decimals, clamped to
    the scorer's (0, 10,000,000) range.

Validation on the kit's practice cases (see README.md):
  * Walk-forward pseudo-validation, 48 targets (6 cases x 8 checkpoints):
    MAE 30,632 cents vs persistence 32,968 cents (-7.1%).
  * Coinbase BTC-USD closes as a proxy for the 6 real practice targets:
    MAE 39,467 cents vs persistence 45,904 cents (-14.0%).

Stdlib only, no network, no randomness, no clock/env reads beyond the two
MAKEFUN_* directory variables. Deterministic: identical input bytes give
identical output bytes. Reads $MAKEFUN_INPUT_DIR (default /input), writes
$MAKEFUN_OUTPUT_DIR (default /output); one <id>.out per <id>.in.
"""

import json
import math
import os
from pathlib import Path

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

MIN_PRICE = 0.00001
MAX_PRICE = 9_999_999.99999

# Model parameters (fixed in advance; chosen on the practice cases, see README).
MOMENTUM_HALFLIFE_MIN = 30.0   # EWMA half-life for 1-minute log returns
MOMENTUM_DAMP = 0.20            # shrinkage on the extrapolated momentum drift
REVERSION_HALFLIFE_MIN = 720.0  # EWMA half-life for the slow log-price level
REVERSION_BETA = 0.08           # pull toward the slow level
DRIFT_CAP = 0.004               # max |log drift| (+/-0.4%)
HORIZON_MIN = 240


def _ewma_last(values, halflife):
    """Last value of an exponentially weighted moving average."""
    alpha = 1.0 - 0.5 ** (1.0 / halflife)
    acc = values[0]
    for value in values[1:]:
        acc += alpha * (value - acc)
    return acc


def forecast(prices):
    """Forecast the close HORIZON_MIN minutes after the last price."""
    if not prices:
        raise ValueError("market has no prices")
    last = prices[-1]
    if not (isinstance(last, (int, float)) and math.isfinite(last)) or last <= 0:
        raise ValueError("market's last price is not a finite positive number")
    if len(prices) < 2:
        # A single price carries no trend information: persistence.
        return round(min(MAX_PRICE, max(MIN_PRICE, last)) * 1e5) / 1e5

    # Log prices, carrying the last valid value forward over any bad tick
    # so one corrupt minute cannot crash the whole case.
    log_prices = []
    last_log = None
    for p in prices:
        if isinstance(p, (int, float)) and math.isfinite(p) and p > 0:
            last_log = math.log(p)
        if last_log is None:
            raise ValueError("market has no valid price")
        log_prices.append(last_log)
    log_returns = [log_prices[i] - log_prices[i - 1] for i in range(1, len(log_prices))]

    # Short-horizon momentum: recent per-minute drift, extrapolated.
    momentum = _ewma_last(log_returns, MOMENTUM_HALFLIFE_MIN)
    # Mean reversion: distance of the log price from its slow level.
    slow_level = _ewma_last(log_prices, REVERSION_HALFLIFE_MIN)
    drift = MOMENTUM_DAMP * momentum * HORIZON_MIN - REVERSION_BETA * (log_prices[-1] - slow_level)
    drift = max(-DRIFT_CAP, min(DRIFT_CAP, drift))

    price = math.exp(log_prices[-1] + drift)
    # Keep on the price grid's 5 decimals and inside the scorer's bounds.
    price = round(min(MAX_PRICE, max(MIN_PRICE, price)) * 1e5) / 1e5
    return price


def main():
    input_dir = Path(INPUT_DIR)
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Name order, so two runs write the same bytes.
    inputs = sorted(p for p in input_dir.iterdir() if p.name.endswith(".in"))
    for path in inputs:
        case_id = path.name[: -len(".in")]
        with path.open("r", encoding="utf-8") as fh:
            case = json.load(fh)
        markets = case.get("markets")
        if not isinstance(markets, list) or len(markets) != 1:
            raise ValueError(f"{path.name} does not hold exactly one market")
        price = forecast(markets[0]["prices"])
        payload = {"forecasts": [{"case": case_id, "price": price}]}
        out_path = output_dir / f"{case_id}.out"
        with out_path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")


if __name__ == "__main__":
    main()
