from __future__ import annotations

import html


def _money_s(amount: float) -> str:
    return f"{amount:.2f} с."


def render_receipt_pre(items: list[dict], total: float, total_label: str = "ИТОГО", width: int = 28) -> str:
    rows: list[tuple[str, str]] = []
    for it in items:
        qty = int(it["quantity"])
        name = str(it["name"])
        line_total = float(it["price"]) * qty
        left = f"{qty} x {name}"
        right = _money_s(line_total)
        rows.append((left, right))

    total_left = total_label
    total_right = _money_s(float(total))

    max_left = max([len(total_left)] + [len(l) for l, _ in rows]) if rows else len(total_left)
    max_right = max([len(total_right)] + [len(r) for _, r in rows]) if rows else len(total_right)
    line_width = max(width, max_left + 2 + max_right)
    sep = "-" * line_width

    def line(left: str, right: str) -> str:
        dots = line_width - len(left) - len(right) - 2
        if dots < 1:
            dots = 1
        return f"{left} {'.' * dots} {right}"

    lines = [sep]
    lines += [line(l, r) for l, r in rows]
    lines += [sep, line(total_left, total_right)]
    return f"<pre>{html.escape(chr(10).join(lines))}</pre>"


def render_receipt_pre_from_order_items(order_items: list[dict], total: float, total_label: str = "ИТОГО", width: int = 28) -> str:
    items = [
        {
            "name": it.get("name") or "",
            "quantity": int(it.get("quantity") or 0),
            "price": float(it.get("price_at_moment") or 0),
        }
        for it in order_items
    ]
    return render_receipt_pre(items=items, total=float(total), total_label=total_label, width=width)
