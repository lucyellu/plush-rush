#!/usr/bin/env python3
"""
prefetch_bars.py — Pre-fetches morning-hour OHLCV bars from Alpaca and bundles
them as static JSON files for game_001.html to load offline.

For each trading day in the last 30 days, fetches 1-min bars between
6:30 AM PT and 7:30 AM PT (US market open hour) for SPY, BTC/USD, GLD.

Outputs:
  data/bars_<SYM>_<YYYY-MM-DD>.json   per (symbol, date)
  data/index.json                      list of available bundles + metadata

Run once to seed. Re-run nightly (cron / Task Scheduler / GitHub Actions) to
keep the bundle current. The game tries the local bundle first, then live
Alpaca, then Yahoo / Binance fallbacks.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
CONFIG_PATH = ROOT / 'config.json'

ALPACA_DATA = 'https://data.alpaca.markets'
DAYS_BACK = 30  # how many calendar days to scan (weekends auto-skipped)

# Symbols: (display_sym, alpaca_sym, is_crypto)
SYMBOLS = [
    ('SPY',     'SPY',     False),
    ('BTC_USD', 'BTC/USD', True),
    ('GLD',     'GLD',     False),
]


def load_keys():
    """Load Alpaca keys from config.json."""
    if not CONFIG_PATH.exists():
        sys.exit(f"Missing {CONFIG_PATH}. Add alpaca_key + alpaca_secret.")
    cfg = json.loads(CONFIG_PATH.read_text())
    key = cfg.get('alpaca_key', '').strip()
    secret = cfg.get('alpaca_secret', '').strip()
    if not key or not secret:
        sys.exit("config.json missing alpaca_key or alpaca_secret")
    return key, secret


def pt_to_utc_iso(date_str: str, hour: int, minute: int) -> str:
    """Convert PT date+time to UTC ISO 8601. Handles PST(-8)/PDT(-7) via dateutil-free arithmetic.

    Strategy: try +7 (PDT) and +8 (PST). The one whose round-trip back to PT
    produces the requested (date, hour, minute) is correct.
    """
    y, m, d = (int(p) for p in date_str.split('-'))
    for offset in (7, 8):
        utc = datetime(y, m, d, hour + offset, minute, tzinfo=timezone.utc)
        # Round-trip: subtract offset back to "PT-as-naive"
        pt_naive = utc - timedelta(hours=offset)
        if (pt_naive.year, pt_naive.month, pt_naive.day,
                pt_naive.hour, pt_naive.minute) == (y, m, d, hour, minute):
            return utc.isoformat().replace('+00:00', 'Z')
    # Fallback to PDT
    return datetime(y, m, d, hour + 7, minute, tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


def trading_days(n_back: int) -> list:
    """Return last n_back weekdays (Mon-Fri) going back from today, in PT.
    Note: doesn't filter US market holidays. Holidays just produce empty bar sets,
    which the game already tolerates (skipped at runtime).
    """
    out = []
    today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-7)))  # approximate PT
    cur = today.date()
    scanned = 0
    while len(out) < n_back and scanned < n_back * 2:
        if cur.weekday() < 5:  # 0=Mon .. 4=Fri
            out.append(cur.strftime('%Y-%m-%d'))
        cur = cur - timedelta(days=1)
        scanned += 1
    return out


def fetch_bars(key: str, secret: str, alpaca_sym: str, is_crypto: bool, date: str) -> list:
    """Fetch 1-min bars for the morning hour on `date`. Returns [] on no-data."""
    start = pt_to_utc_iso(date, 6, 30)
    end   = pt_to_utc_iso(date, 7, 30)
    if is_crypto:
        params = {
            'symbols': alpaca_sym,
            'timeframe': '1Min',
            'start': start,
            'end': end,
            'limit': '120',
        }
        url = f'{ALPACA_DATA}/v1beta3/crypto/us/bars?' + urlencode(params)
    else:
        params = {
            'timeframe': '1Min',
            'start': start,
            'end': end,
            'limit': '120',
            'feed': 'iex',
            'adjustment': 'raw',
        }
        url = f'{ALPACA_DATA}/v2/stocks/{alpaca_sym}/bars?' + urlencode(params)

    req = Request(url, headers={
        'APCA-API-KEY-ID': key,
        'APCA-API-SECRET-KEY': secret,
    })
    try:
        with urlopen(req, timeout=15) as r:
            payload = json.loads(r.read().decode('utf-8'))
    except HTTPError as e:
        body = ''
        try: body = e.read().decode('utf-8', errors='replace')[:200]
        except Exception: pass
        print(f'  ! HTTP {e.code} for {alpaca_sym} {date}: {body}')
        return []
    except URLError as e:
        print(f'  ! Network error for {alpaca_sym} {date}: {e}')
        return []

    if is_crypto:
        return (payload.get('bars') or {}).get(alpaca_sym, []) or []
    return payload.get('bars', []) or []


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    key, secret = load_keys()
    days = trading_days(DAYS_BACK)
    print(f'Prefetch window: {len(days)} trading days, {len(SYMBOLS)} symbols')
    index = {'updated': datetime.now(timezone.utc).isoformat(), 'bundles': []}
    written = 0
    skipped = 0
    for display_sym, alpaca_sym, is_crypto in SYMBOLS:
        for date in days:
            out_path = DATA_DIR / f'bars_{display_sym}_{date}.json'
            # Skip if already present and looks valid (cheap freshness check)
            if out_path.exists():
                try:
                    cached = json.loads(out_path.read_text())
                    if cached.get('bars') and len(cached['bars']) >= 5:
                        index['bundles'].append({
                            'sym': display_sym, 'date': date, 'bar_count': len(cached['bars']),
                        })
                        skipped += 1
                        continue
                except Exception:
                    pass
            print(f'  fetching {display_sym} {date} ...', end=' ', flush=True)
            bars = fetch_bars(key, secret, alpaca_sym, is_crypto, date)
            print(f'{len(bars)} bars')
            if not bars:
                # Save an empty marker so we don't re-hit Alpaca for known-empty days
                out_path.write_text(json.dumps({'sym': display_sym, 'date': date, 'bars': [], 'fetched': datetime.now(timezone.utc).isoformat()}))
                continue
            out_path.write_text(json.dumps({
                'sym': display_sym,
                'date': date,
                'bars': bars,
                'fetched': datetime.now(timezone.utc).isoformat(),
            }))
            index['bundles'].append({
                'sym': display_sym, 'date': date, 'bar_count': len(bars),
            })
            written += 1
            # Be nice to the API
            time.sleep(0.15)
    (DATA_DIR / 'index.json').write_text(json.dumps(index, indent=2))
    print(f'Done. Wrote {written} new bundles, kept {skipped} cached.')
    print(f'Index: {DATA_DIR / "index.json"}')


if __name__ == '__main__':
    main()
