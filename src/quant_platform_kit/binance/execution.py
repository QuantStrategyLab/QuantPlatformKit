from __future__ import annotations

import math


def format_qty(client, symbol, qty):
    try:
        info = client.get_symbol_info(symbol)
        step_size = float([f["stepSize"] for f in info["filters"] if f["filterType"] == "LOT_SIZE"][0])
        precision = int(round(-math.log(step_size, 10), 0))
        return round(math.floor(qty / step_size) * step_size, precision)
    except Exception:
        return round(math.floor(qty * 10000) / 10000, 4)
