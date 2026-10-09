"""حساب التقارير الأسبوعية والشهرية من الطلبات."""

from collections import defaultdict
from datetime import date, timedelta

import finance
import sample_data as sample

MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
KINDS = {"week": "أسبوعي", "month": "شهري"}

# أول طلب لكل عميل، عشان نفرّق بين العميل الجديد والعائد
FIRST_ORDER = {}
for _o in reversed(sample.ALL_ORDERS):
    if _o["status"] != "ملغي":
        FIRST_ORDER.setdefault(_o["customer_id"], _o["date"])


def week_start(d):
    """الأسبوع من الأحد للسبت."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _fmt_day(d, with_year=False):
    s = f"{d.day} {MONTHS[d.month - 1]}"
    return f"{s} {d.year}" if with_year else s


def periods(kind):
    """كل الفترات المتاحة، الأحدث أولاً."""
    today = date.today()
    first = date.fromisoformat(sample.ALL_ORDERS[-1]["date"])
    out = []
    if kind == "week":
        start = week_start(today)
        while start + timedelta(days=6) >= first:
            end = start + timedelta(days=6)
            label = f"{_fmt_day(start)} – {_fmt_day(end, True)}"
            out.append({"key": start.isoformat(), "label": label, "short": _fmt_day(start),
                        "start": start, "end": end, "partial": end > today or start < first})
            start -= timedelta(days=7)
    else:
        y, m = today.year, today.month
        while date(y, m, 1) >= date(first.year, first.month, 1):
            start = date(y, m, 1)
            end = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
            out.append({"key": f"{y}-{m:02d}", "label": f"{MONTHS[m - 1]} {y}", "short": MONTHS[m - 1],
                        "start": start, "end": end, "partial": end > today or start < first})
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out


def find_period(kind, key):
    items = periods(kind)
    for i, p in enumerate(items):
        if p["key"] == key:
            return p, (items[i + 1] if i + 1 < len(items) else None)
    return items[0], (items[1] if len(items) > 1 else None)


def orders_in(period, store):
    s, e = period["start"].isoformat(), period["end"].isoformat()
    return [o for o in sample.for_store(sample.ALL_ORDERS, store) if s <= o["date"] <= e]


def summarize(orders, period=None):
    live = [o for o in orders if o["status"] != "ملغي"]
    cancelled = len(orders) - len(live)
    total = lambda k: sum(o[k] for o in live)
    m = {
        "orders": len(live),
        "cancelled": cancelled,
        "cancel_rate": cancelled / len(orders) * 100 if orders else 0,
        "gross": total("total"),
        "subtotal": total("subtotal"),
        "discount": total("discount"),
        "shipping": total("shipping"),
        "vat": total("vat"),
        "net": total("net"),
        "merch_ex_vat": total("merch_ex_vat"),
        "ship_ex_vat": total("ship_ex_vat"),
        "cogs": total("cogs"),
        "ship_cost": total("ship_cost"),
        "pay_fee": total("pay_fee"),
        "profit": total("profit"),
        "items": total("qty"),
        "free_ship": sum(1 for o in live if o["shipping"] == 0),
    }
    m["gross_profit"] = m["merch_ex_vat"] - m["cogs"]
    m["ship_net"] = m["ship_ex_vat"] - m["ship_cost"]
    m["margin"] = m["profit"] / m["net"] * 100 if m["net"] else 0
    m["aov"] = m["gross"] / m["orders"] if m["orders"] else 0
    m["items_per_order"] = m["items"] / m["orders"] if m["orders"] else 0
    m["discount_rate"] = m["discount"] / m["subtotal"] * 100 if m["subtotal"] else 0
    customers = {o["customer_id"] for o in live}
    m["customers"] = len(customers)
    if period:
        s, e = period["start"].isoformat(), period["end"].isoformat()
        m["new_customers"] = sum(1 for c in customers if s <= FIRST_ORDER.get(c, "") <= e)
    else:
        m["new_customers"] = 0
    m["returning_customers"] = m["customers"] - m["new_customers"]
    return m


def statement(m):
    """قائمة الدخل المختصرة: من إجمالي المبيعات لصافي الربح."""
    return [
        {"label": "إجمالي المبيعات (شامل الضريبة والشحن)", "value": m["gross"], "kind": "total"},
        {"label": f"ضريبة القيمة المضافة {round(finance.VAT_RATE * 100)}%", "value": -m["vat"], "kind": "minus"},
        {"label": "صافي الإيرادات بدون ضريبة", "value": m["net"], "kind": "subtotal"},
        {"label": "منها مبيعات المنتجات", "value": m["merch_ex_vat"], "kind": "detail"},
        {"label": "منها إيراد الشحن", "value": m["ship_ex_vat"], "kind": "detail"},
        {"label": "تكلفة البضاعة المباعة", "value": -m["cogs"], "kind": "minus"},
        {"label": "تكلفة شركات الشحن", "value": -m["ship_cost"], "kind": "minus"},
        {"label": "رسوم بوابات الدفع", "value": -m["pay_fee"], "kind": "minus"},
        {"label": "صافي الربح التقديري", "value": m["profit"], "kind": "result"},
    ]


def by_product(orders):
    rows = defaultdict(lambda: {"qty": 0, "sales": 0.0, "cost": 0.0, "orders": 0})
    names, stores = {}, {}
    for o in orders:
        if o["status"] == "ملغي":
            continue
        for l in o["lines"]:
            r = rows[l["product_id"]]
            r["qty"] += l["qty"]
            r["sales"] += l["qty"] * l["price"]
            r["cost"] += l["qty"] * l["cost"]
            r["orders"] += 1
            names[l["product_id"]], stores[l["product_id"]] = l["name"], o["store"]
    out = []
    for pid, r in rows.items():
        sales_ex = finance.ex_vat(r["sales"])
        out.append({"name": names[pid], "store": stores[pid], "qty": r["qty"], "orders": r["orders"],
                    "sales": r["sales"], "profit": sales_ex - r["cost"],
                    "margin": (sales_ex - r["cost"]) / sales_ex * 100 if sales_ex else 0})
    return sorted(out, key=lambda r: r["sales"], reverse=True)


def by_field(orders, field):
    rows = defaultdict(lambda: {"orders": 0, "sales": 0.0})
    for o in orders:
        if o["status"] == "ملغي":
            continue
        rows[o[field]]["orders"] += 1
        rows[o[field]]["sales"] += o["total"]
    total = sum(r["sales"] for r in rows.values()) or 1
    out = [{"name": k, "orders": r["orders"], "sales": r["sales"], "share": r["sales"] / total * 100}
           for k, r in rows.items()]
    return sorted(out, key=lambda r: r["sales"], reverse=True)


def by_carrier(orders):
    rows = defaultdict(lambda: {"orders": 0, "cost": 0.0, "days": 0, "delivered": 0, "late": 0})
    for o in orders:
        if o["status"] == "ملغي":
            continue
        r = rows[o["carrier"]]
        r["orders"] += 1
        r["cost"] += o["ship_cost"]
        if o["status"] == "تم التسليم":
            r["delivered"] += 1
            r["days"] += o["delivery_days"]
            r["late"] += o["delivery_days"] > finance.DELIVERY_SLA_DAYS
    out = []
    for name, r in rows.items():
        out.append({"name": name, "orders": r["orders"], "avg_cost": r["cost"] / r["orders"],
                    "avg_days": r["days"] / r["delivered"] if r["delivered"] else 0,
                    "late_rate": r["late"] / r["delivered"] * 100 if r["delivered"] else 0})
    return sorted(out, key=lambda r: r["orders"], reverse=True)


def trend(kind, store, count=None):
    """إجماليات آخر الفترات للرسم البياني، الأقدم أولاً."""
    count = count or (12 if kind == "week" else 6)
    stores = ["smooth", "glorias"] if store == "all" else [store]
    out = []
    for p in reversed(periods(kind)[:count]):
        row = {"key": p["key"], "label": p["short"], "full": p["label"], "partial": p["partial"]}
        for s in stores:
            m = summarize(orders_in(p, s))
            row[s] = round(m["gross"])
            row[s + "_net"] = round(m["net"])
            row[s + "_profit"] = round(m["profit"])
            row[s + "_orders"] = m["orders"]
        out.append(row)
    return out


def change(cur, prev):
    """نسبة التغيير، أو None لو مفيش فترة سابقة."""
    if prev is None or not prev:
        return None
    return (cur - prev) / abs(prev) * 100


def build(kind, key, store):
    kind = kind if kind in KINDS else "month"
    period, prev_period = find_period(kind, key)
    orders = orders_in(period, store)
    m = summarize(orders, period)
    pm = summarize(orders_in(prev_period, store), prev_period) if prev_period else None
    deltas = {k: change(m[k], pm[k] if pm else None)
              for k in ("gross", "net", "orders", "aov", "profit", "vat", "ship_net", "customers")}
    return {
        "kind": kind,
        "kinds": KINDS,
        "period": period,
        "prev_period": prev_period,
        "periods": periods(kind),
        "m": m,
        "pm": pm,
        "deltas": deltas,
        "statement": statement(m),
        "products": by_product(orders),
        "cities": by_field(orders, "city"),
        "payments": by_field(orders, "payment"),
        "carriers": by_carrier(orders),
        "sources": by_field(orders, "source"),
        "stores_split": by_field(orders, "store") if store == "all" else [],
        "orders": orders,
        "trend": trend(kind, store),
    }
