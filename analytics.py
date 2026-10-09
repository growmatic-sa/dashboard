"""تحليلات دعم القرار: المخزون، المنتجات، العملاء، التسويق، الشحن، والتوقعات.

كل الدوال بتاخد المتجر ('all' أو مفتاح متجر) وبتشتغل على الطلبات غير الملغية.
"""

import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from itertools import combinations

import finance
import sample_data as sample

DAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def today():
    return date.today()


def live(store, days=None, end=None):
    """الطلبات غير الملغية لآخر عدد أيام."""
    end = end or today()
    start = (end - timedelta(days=days - 1)).isoformat() if days else "0000"
    e = end.isoformat()
    return [o for o in sample.for_store(sample.ALL_ORDERS, store)
            if o["status"] != "ملغي" and start <= o["date"] <= e]


# ---------------- المخزون ----------------

def inventory_plan(store, window=30):
    sold = defaultdict(int)
    for o in live(store, window):
        for l in o["lines"]:
            sold[l["product_id"]] += l["qty"]
    out = []
    for p in sample.for_store(sample.PRODUCTS, store):
        velocity = sold[p["id"]] / window
        cover = p["stock"] / velocity if velocity else math.inf
        reorder_point = velocity * (finance.LEAD_TIME_DAYS + finance.SAFETY_DAYS)
        need = velocity * (finance.LEAD_TIME_DAYS + finance.TARGET_COVER_DAYS) - p["stock"]
        qty = int(math.ceil(max(0, need) / 5) * 5)
        if p["stock"] == 0 and velocity:
            state = "out"
        elif p["stock"] <= reorder_point:
            state = "reorder"
        elif cover <= finance.LEAD_TIME_DAYS + finance.SAFETY_DAYS + 7:
            state = "soon"
        elif cover > 90:
            state = "over"
        else:
            state = "ok"
        out.append(dict(p, velocity=velocity, cover=cover, reorder_qty=qty if state in ("out", "reorder", "soon") else 0,
                        reorder_cash=qty * p["cost"] if state in ("out", "reorder", "soon") else 0,
                        lost_per_day=velocity * p["price"] if state == "out" else 0,
                        stockout_date=(today() + timedelta(days=int(cover))) if velocity and cover != math.inf else None,
                        state=state))
    order = {"out": 0, "reorder": 1, "soon": 2, "ok": 3, "over": 4}
    return sorted(out, key=lambda r: (order[r["state"]], r["cover"]))


# ---------------- المنتجات ----------------

def abc(store, window=90):
    """تصنيف ABC: A = المنتجات اللي بتجيب أول 80% من المبيعات."""
    rev = defaultdict(float)
    qty = defaultdict(int)
    for o in live(store, window):
        for l in o["lines"]:
            rev[l["product_id"]] += l["qty"] * l["price"]
            qty[l["product_id"]] += l["qty"]
    total = sum(rev.values()) or 1
    rows, cum = [], 0
    by_id = {p["id"]: p for p in sample.PRODUCTS}
    for pid, r in sorted(rev.items(), key=lambda kv: kv[1], reverse=True):
        cum += r
        share = cum / total * 100
        cls = "A" if share - r / total * 100 < 80 else ("B" if share - r / total * 100 < 95 else "C")
        p = by_id[pid]
        rows.append({"name": p["name"], "store": p["store"], "revenue": r, "qty": qty[pid], "share": r / total * 100,
                     "cum": share, "cls": cls, "margin": (finance.ex_vat(p["price"]) - p["cost"]) / finance.ex_vat(p["price"]) * 100})
    return rows


def basket_pairs(store, window=90, top=6):
    """المنتجات اللي بتتشرى مع بعض، مع الـ lift (أكبر من 1 = علاقة حقيقية)."""
    orders = [o for o in live(store, window)]
    n = len(orders) or 1
    single = Counter()
    pairs = Counter()
    names = {}
    for o in orders:
        ids = sorted({l["product_id"] for l in o["lines"]})
        for l in o["lines"]:
            names[l["product_id"]] = l["name"]
        single.update(ids)
        pairs.update(combinations(ids, 2))
    out = []
    for (a, b), c in pairs.items():
        if c < 5:
            continue
        lift = (c / n) / ((single[a] / n) * (single[b] / n))
        out.append({"a": names[a], "b": names[b], "count": c, "lift": lift,
                    "conf": c / single[a] * 100})
    return sorted(out, key=lambda r: (r["lift"] * math.log(r["count"] + 1)), reverse=True)[:top]


# ---------------- العملاء ----------------

SEGMENTS = {
    "champions": {"label": "أبطال", "tone": "ok", "action": "كافئهم ببرنامج ولاء أو منتج حصري، واطلب منهم تقييمات."},
    "loyal": {"label": "مخلصون", "tone": "info", "action": "اعرض عليهم باقات ومنتجات مكمّلة لرفع قيمة السلة."},
    "new": {"label": "جدد واعدون", "tone": "brand", "action": "رسالة ترحيب وكوبون للطلب التاني خلال 30 يوم."},
    "at_risk": {"label": "معرّضون للفقد", "tone": "warn", "action": "حملة استرجاع بخصم محدود المدة قبل ما يروحوا للمنافس."},
    "lost": {"label": "مفقودون", "tone": "danger", "action": "عرض قوي مرة واحدة، ولو ما رجعوش وقّف الصرف عليهم."},
    "regular": {"label": "يحتاجون اهتمام", "tone": "neutral", "action": "محتوى ومنتجات جديدة تشجّعهم على الطلب التاني."},
}


def customers(store):
    data = {}
    for o in live(store):
        c = data.setdefault(o["customer_id"], {"id": o["customer_id"], "name": o["customer"], "city": o["city"],
                                              "store": o["store"], "orders": 0, "spent": 0.0, "profit": 0.0,
                                              "first": o["date"], "last": o["date"]})
        c["orders"] += 1
        c["spent"] += o["total"]
        c["profit"] += o["profit"]
        c["first"] = min(c["first"], o["date"])
        c["last"] = max(c["last"], o["date"])
    t = today()
    for c in data.values():
        r = (t - date.fromisoformat(c["last"])).days
        c["recency"] = r
        f = c["orders"]
        if f >= 4 and r <= 30:
            seg = "champions"
        elif f >= 3 and r <= 60:
            seg = "loyal"
        elif f == 1 and r <= 30:
            seg = "new"
        elif f >= 2 and 45 < r <= 120:
            seg = "at_risk"
        elif r > 120:
            seg = "lost"
        else:
            seg = "regular"
        c["segment"] = seg
    return list(data.values())


def segment_summary(custs):
    total_rev = sum(c["spent"] for c in custs) or 1
    out = []
    for key, meta in SEGMENTS.items():
        group = [c for c in custs if c["segment"] == key]
        rev = sum(c["spent"] for c in group)
        out.append(dict(meta, key=key, count=len(group), revenue=rev, share=rev / total_rev * 100,
                        avg=rev / len(group) if group else 0,
                        pct=len(group) / (len(custs) or 1) * 100))
    return out


def cohorts(store, months=6):
    """نسبة العملاء اللي رجعوا يشتروا بعد أول شهر لهم."""
    orders = live(store)
    first = {}
    for o in sorted(orders, key=lambda o: o["date"]):
        first.setdefault(o["customer_id"], o["date"][:7])
    active = defaultdict(set)  # (cohort, offset) -> customers
    for o in orders:
        c = first[o["customer_id"]]
        cy, cm = map(int, c.split("-"))
        oy, om = map(int, o["date"][:7].split("-"))
        active[(c, (oy - cy) * 12 + (om - cm))].add(o["customer_id"])
    t = today()
    keys = []
    y, m = t.year, t.month
    for _ in range(months):
        keys.append(f"{y}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    keys.reverse()
    rows = []
    for k in keys:
        size = len(active.get((k, 0), set()))
        y, m = map(int, k.split("-"))
        max_off = (t.year - y) * 12 + (t.month - m)
        cells = []
        for off in range(1, months):
            if off > max_off:
                cells.append(None)
            else:
                cells.append(len(active.get((k, off), set())) / size * 100 if size else 0)
        rows.append({"label": f"{MONTHS_AR[m - 1]} {y}", "size": size, "cells": cells})
    return rows


def repeat_stats(custs):
    repeaters = [c for c in custs if c["orders"] > 1]
    gaps = []
    for c in repeaters:
        span = (date.fromisoformat(c["last"]) - date.fromisoformat(c["first"])).days
        gaps.append(span / (c["orders"] - 1))
    return {
        "repeat_rate": len(repeaters) / (len(custs) or 1) * 100,
        "avg_gap": sum(gaps) / len(gaps) if gaps else 0,
        "clv": sum(c["spent"] for c in custs) / (len(custs) or 1),
        "clv_profit": sum(c["profit"] for c in custs) / (len(custs) or 1),
    }


# ---------------- التسويق ----------------

def marketing(store, window=30):
    orders = live(store, window)
    stores = ["smooth", "glorias"] if store == "all" else [store]
    end = today()
    dates = {(end - timedelta(days=i)).isoformat() for i in range(window)}
    spend = defaultdict(float)
    for (d, s, ch), v in sample.AD_SPEND.items():
        if d in dates and s in stores:
            spend[ch] += v
    first = {}
    for o in sorted(sample.for_store(sample.ALL_ORDERS, store), key=lambda o: o["date"]):
        if o["status"] != "ملغي":
            first.setdefault(o["customer_id"], o["id"])
    rows = {}
    for ch in finance.AD_CHANNELS + [finance.ORGANIC]:
        rows[ch] = {"name": ch, "spend": spend.get(ch, 0.0), "orders": 0, "revenue": 0.0, "profit": 0.0, "new": 0}
    for o in orders:
        r = rows[o["source"]]
        r["orders"] += 1
        r["revenue"] += o["total"]
        r["profit"] += o["profit"]
        if first.get(o["customer_id"]) == o["id"]:
            r["new"] += 1
    for r in rows.values():
        r["roas"] = r["revenue"] / r["spend"] if r["spend"] else None
        r["cac"] = r["spend"] / r["new"] if r["new"] and r["spend"] else None
        r["net"] = r["profit"] - r["spend"]
    total_spend = sum(spend.values())
    total_rev = sum(o["total"] for o in orders)
    total_profit = sum(o["profit"] for o in orders)
    new_total = sum(r["new"] for r in rows.values())
    return {
        "channels": sorted([r for r in rows.values() if r["spend"]], key=lambda r: r["roas"] or 0, reverse=True),
        "organic": rows[finance.ORGANIC],
        "spend": total_spend,
        "revenue": total_rev,
        "mer": total_rev / total_spend if total_spend else 0,
        "profit_after_ads": total_profit - total_spend,
        "profit_before_ads": total_profit,
        "cac": total_spend / new_total if new_total else 0,
        "new_customers": new_total,
        "ad_share": total_spend / total_rev * 100 if total_rev else 0,
    }


def coupons(store, window=90):
    rows = {}
    for o in live(store, window):
        if not o["coupon"]:
            continue
        key = (o["coupon"], o["store"])
        r = rows.setdefault(key, {"code": o["coupon"], "store": o["store"], "uses": 0, "revenue": 0.0, "discount": 0.0, "profit": 0.0,
                                  "influencer": sample.COUPONS[o["store"]][o["coupon"]][1],
                                  "rate": sample.COUPONS[o["store"]][o["coupon"]][0] * 100})
        r["uses"] += 1
        r["revenue"] += o["total"]
        r["discount"] += o["discount"]
        r["profit"] += o["profit"]
    out = list(rows.values())
    for r in out:
        r["aov"] = r["revenue"] / r["uses"]
        r["profit_per_order"] = r["profit"] / r["uses"]
    return sorted(out, key=lambda r: r["revenue"], reverse=True)


def heatmap(store, window=90):
    """عدد الطلبات حسب اليوم والساعة (مجمّعة كل 3 ساعات)."""
    grid = [[0] * 8 for _ in range(7)]
    for o in live(store, window):
        wd = (date.fromisoformat(o["date"]).weekday() + 1) % 7  # الأحد أولاً
        grid[wd][o["hour"] // 3] += 1
    days = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"]
    slots = [f"{h:02d}–{h + 3:02d}" for h in range(0, 24, 3)]
    peak = max(max(r) for r in grid) or 1
    best = max(((d, s) for d in range(7) for s in range(8)), key=lambda ds: grid[ds[0]][ds[1]])
    return {"days": days, "slots": slots, "grid": grid, "peak": peak,
            "best": {"day": days[best[0]], "slot": slots[best[1]], "count": grid[best[0]][best[1]]}}


# ---------------- الشحن ----------------

def carriers(store, window=60):
    rows = {}
    for o in live(store, window):
        r = rows.setdefault(o["carrier"], {"name": o["carrier"], "orders": 0, "cost": 0.0, "days": 0, "late": 0, "delivered": 0})
        r["orders"] += 1
        r["cost"] += o["ship_cost"]
        if o["status"] == "تم التسليم":
            r["delivered"] += 1
            r["days"] += o["delivery_days"]
            r["late"] += o["delivery_days"] > finance.DELIVERY_SLA_DAYS
    out = []
    for r in rows.values():
        r["avg_cost"] = r["cost"] / r["orders"]
        r["avg_days"] = r["days"] / r["delivered"] if r["delivered"] else 0
        r["late_rate"] = r["late"] / r["delivered"] * 100 if r["delivered"] else 0
        out.append(r)
    return sorted(out, key=lambda r: r["orders"], reverse=True)


def delayed_orders(store):
    t = today()
    out = []
    for o in sample.for_store(sample.ALL_ORDERS, store):
        if o["status"] in ("جديد", "قيد التجهيز"):
            age = (t - date.fromisoformat(o["date"])).days
            if age > finance.PROCESSING_SLA_DAYS:
                out.append(dict(o, age=age))
    return sorted(out, key=lambda o: o["age"], reverse=True)


# ---------------- الأهداف والتوقعات ----------------

def month_progress(store, target):
    t = today()
    start = t.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    days_in_month = (next_month - start).days
    elapsed = t.day
    mtd_orders = [o for o in live(store, elapsed)]
    mtd = sum(o["total"] for o in mtd_orders)
    mtd_profit = sum(o["profit"] for o in mtd_orders)
    last14 = sum(o["total"] for o in live(store, 14)) / 14
    remaining = days_in_month - elapsed
    projected = mtd + last14 * remaining
    return {
        "target": target,
        "mtd": mtd,
        "mtd_profit": mtd_profit,
        "pct": mtd / target * 100 if target else 0,
        "projected": projected,
        "projected_pct": projected / target * 100 if target else 0,
        "run_rate": last14,
        "required_daily": max(0, (target - mtd) / remaining) if remaining else 0,
        "remaining_days": remaining,
        "elapsed": elapsed,
        "days_in_month": days_in_month,
        "time_pct": elapsed / days_in_month * 100,
        "month_label": f"{MONTHS_AR[t.month - 1]} {t.year}",
    }


def monthly_history(store, months=6):
    """إجمالي مبيعات آخر شهور مكتملة، لاقتراح الأهداف ومقارنتها."""
    t = today()
    out = []
    y, m = t.year, t.month
    for _ in range(months):
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        key = f"{y}-{m:02d}"
        total = sum(o["total"] for o in sample.for_store(sample.ALL_ORDERS, store)
                    if o["status"] != "ملغي" and o["date"].startswith(key))
        out.append({"key": key, "label": MONTHS_AR[m - 1], "total": total})
    out.reverse()
    return out


def suggested_target(store):
    hist = [h["total"] for h in monthly_history(store, 3) if h["total"]]
    base = hist[-1] if hist else 0
    return int(round(base * 1.10 / 1000) * 1000)


# ---------------- بيانات المحاكي ----------------

def simulator_baseline(store, window=30):
    """طلبات آخر 30 يوم بشكل مختصر عشان المحاكي يعيد الحساب في المتصفح."""
    orders = live(store, window)
    m = marketing(store, window)
    rows = [[o["store"], round(o["subtotal"] - o["discount"], 2), o["discount"], o["shipping"], round(o["cogs"], 2),
             o["ship_cost"], round(o["pay_fee"] / o["total"], 4) if o["total"] else 0] for o in orders]
    return {
        "orders": rows,
        "window": window,
        "ad_spend": m["spend"],
        "ad_revenue": sum(c["revenue"] for c in m["channels"]),
        "vat": finance.VAT_RATE,
        "elasticity": finance.PRICE_ELASTICITY,
        "ad_marginal": finance.AD_MARGINAL_FACTOR,
        "free_over": finance.FREE_SHIPPING_OVER,
        "fee": finance.SHIPPING_FEE,
    }
