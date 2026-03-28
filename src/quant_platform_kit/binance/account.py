from __future__ import annotations

import time


def get_total_balance(
    client,
    asset,
    *,
    on_spot_error=None,
    on_earn_error=None,
    balance_error_cls=RuntimeError,
):
    total = 0.0
    spot_error = None
    try:
        spot_info = client.get_asset_balance(asset=asset)
        total += float(spot_info["free"]) + float(spot_info["locked"])
    except Exception as exc:
        spot_error = exc
        if on_spot_error is not None:
            on_spot_error(exc)

    try:
        earn_positions = client.get_simple_earn_flexible_product_position(asset=asset)
        if earn_positions and "rows" in earn_positions and len(earn_positions["rows"]) > 0:
            total += float(earn_positions["rows"][0]["totalAmount"])
    except Exception as exc:
        if on_earn_error is not None:
            on_earn_error(exc)

    if spot_error is not None:
        raise balance_error_cls(f"{asset} spot balance unavailable: {spot_error}")
    return total


def ensure_asset_available(
    client,
    asset,
    required_amount,
    *,
    on_redeem=None,
    on_error=None,
    sleep_fn=time.sleep,
):
    try:
        spot_free = float(client.get_asset_balance(asset=asset)["free"])
        if spot_free >= required_amount:
            return True

        shortfall = required_amount - spot_free
        earn_positions = client.get_simple_earn_flexible_product_position(asset=asset)

        if earn_positions and "rows" in earn_positions and len(earn_positions["rows"]) > 0:
            row = earn_positions["rows"][0]
            product_id = row["productId"]
            earn_free = float(row["totalAmount"])

            if earn_free > 0:
                redeem_amt = round(min(shortfall * 1.001, earn_free), 8)
                client.redeem_simple_earn_flexible_product(productId=product_id, amount=redeem_amt)
                if on_redeem is not None:
                    on_redeem(redeem_amt)
                sleep_fn(3)
                return True
    except Exception as exc:
        if on_error is not None:
            on_error(exc)
    return False


def manage_usdt_earn_buffer(
    client,
    target_buffer,
    *,
    on_subscribe=None,
    on_redeem=None,
    on_error=None,
):
    try:
        asset = "USDT"
        spot_free = float(client.get_asset_balance(asset=asset)["free"])

        earn_list = client.get_simple_earn_flexible_product_list(asset=asset)
        if not earn_list or "rows" not in earn_list or len(earn_list["rows"]) == 0:
            return
        product_id = earn_list["rows"][0]["productId"]

        if spot_free > target_buffer + 5.0:
            excess = round(spot_free - target_buffer, 4)
            if excess >= 0.1:
                client.subscribe_simple_earn_flexible_product(productId=product_id, amount=excess)
                if on_subscribe is not None:
                    on_subscribe(excess)
        elif spot_free < target_buffer - 5.0:
            shortfall = round(target_buffer - spot_free, 4)
            earn_positions = client.get_simple_earn_flexible_product_position(asset=asset)
            if earn_positions and "rows" in earn_positions and len(earn_positions["rows"]) > 0:
                earn_free = float(earn_positions["rows"][0]["totalAmount"])
                if earn_free > 0:
                    redeem_amt = round(min(shortfall, earn_free), 8)
                    client.redeem_simple_earn_flexible_product(productId=product_id, amount=redeem_amt)
                    if on_redeem is not None:
                        on_redeem(redeem_amt)
    except Exception as exc:
        if on_error is not None:
            on_error(exc)
