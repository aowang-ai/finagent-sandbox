#!/usr/bin/env python3
"""Keep ~/.grok/auth.json OIDC access tokens fresh during long suite runs."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runners.grok import (  # noqa: E402
    AUTH_JSON,
    _auth_record,
    _ttl_seconds,
    refresh_xai_api_key,
)


def main() -> int:
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    while True:
        try:
            refresh_xai_api_key(force=False)
            blob = json.loads(AUTH_JSON.read_text(encoding="utf-8"))
            _, rec = _auth_record(blob if isinstance(blob, dict) else {})
            ttl = _ttl_seconds(rec) if rec else None
            print(
                f"ts={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} "
                f"ttl={ttl} expires={rec.get('expires_at')}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                f"ts={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} refresh_err={exc}",
                flush=True,
            )
        time.sleep(interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
