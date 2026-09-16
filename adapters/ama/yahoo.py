"""Yahoo Finance chart fetch (stdlib). Used when AMA/FINSABER need prices without vendor keys."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

CRYPTO_YAHOO = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "ADA": "ADA-USD",
    "SOL": "SOL-USD",
    "DOT": "DOT-USD",
    "LINK": "LINK-USD",
    "UNI": "UNI-USD",
    "MATIC": "MATIC-USD",
    "AVAX": "AVAX-USD",
    "ATOM": "ATOM-USD",
}


def yahoo_symbol(asset: str) -> str:
    return CRYPTO_YAHOO.get(asset.upper(), asset.upper())


def is_crypto(asset: str) -> bool:
    return asset.upper() in CRYPTO_YAHOO


def _unix(date_str: str, end_of_day: bool = False) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return int(dt.timestamp())


def fetch_daily_bars(asset: str, date_from: str, date_to: str, *, timeout: int = 30) -> dict[str, float]:
    """Return {YYYY-MM-DD: close} for the inclusive window. Empty dict on failure."""

    symbol = yahoo_symbol(asset)
    params = urllib.parse.urlencode(
        {
            "period1": str(_unix(date_from) - 86400 * 5),
            "period2": str(_unix(date_to, end_of_day=True) + 86400 * 2),
            "interval": "1d",
            "events": "div,splits",
        }
    )
    url = f"{YAHOO_CHART.format(symbol=urllib.parse.quote(symbol))}?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "finagent-sandbox/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return {}
    try:
        result = payload["chart"]["result"][0]
        ts = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        closes = quote.get("close") or []
        adj = (result["indicators"].get("adjclose") or [{}])[0].get("adjclose")
        prices = adj if adj else closes
    except (KeyError, IndexError, TypeError):
        return {}
    out: dict[str, float] = {}
    for t, px in zip(ts, prices):
        if px is None:
            continue
        day = datetime.fromtimestamp(int(t), tz=timezone.utc).strftime("%Y-%m-%d")
        out[day] = float(px)
    return out


def fetch_many(
    assets: list[str],
    date_from: str,
    date_to: str,
    *,
    pause_s: float = 0.15,
) -> dict[str, dict[str, float]]:
    table: dict[str, dict[str, float]] = {}
    for i, asset in enumerate(assets):
        table[asset] = fetch_daily_bars(asset, date_from, date_to)
        if pause_s and i + 1 < len(assets):
            time.sleep(pause_s)
    return table


def price_on_or_before(series: dict[str, float], date_str: str) -> float | None:
    if date_str in series:
        return series[date_str]
    prior = [d for d in series if d <= date_str]
    if not prior:
        return None
    return series[max(prior)]
