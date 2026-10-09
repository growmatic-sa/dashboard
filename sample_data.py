"""بيانات تجريبية للعرض فقط. تُستبدل ببيانات سلة الحقيقية في المرحلة الجاية.

بنولّد 6 شهور من الطلبات لكل متجر، وكل الأرقام (اليومية والتقارير) بتتحسب منها.
"""

import random
from collections import defaultdict
from datetime import date, timedelta

import finance

HISTORY_DAYS = 180

PRODUCTS = [
    {"id": 1, "name": "سيروم فيتامين C", "category": "العناية بالبشرة", "store": "smooth", "price": 189, "cost": 62, "stock": 95, "status": "active"},
    {"id": 2, "name": "كريم ترطيب يومي", "category": "العناية بالبشرة", "store": "smooth", "price": 145, "cost": 48, "stock": 60, "status": "active"},
    {"id": 3, "name": "ماسك طين للبشرة الدهنية", "category": "ماسكات", "store": "smooth", "price": 75, "cost": 22, "stock": 0, "status": "active"},
    {"id": 4, "name": "غسول لطيف يومي", "category": "منظفات", "store": "smooth", "price": 95, "cost": 30, "stock": 340, "status": "active"},
    {"id": 5, "name": "واقي شمس SPF 50", "category": "العناية بالبشرة", "store": "smooth", "price": 120, "cost": 41, "stock": 650, "status": "active"},
    {"id": 6, "name": "تونر الورد", "category": "منظفات", "store": "smooth", "price": 85, "cost": 26, "stock": 210, "status": "active"},
    {"id": 7, "name": "رموش صناعية كثيفة", "category": "رموش", "store": "glorias", "price": 59, "cost": 14, "stock": 40, "status": "active"},
    {"id": 8, "name": "غراء رموش شفاف", "category": "أدوات", "store": "glorias", "price": 49, "cost": 11, "stock": 180, "status": "active"},
    {"id": 9, "name": "مزيل غراء آمن", "category": "أدوات", "store": "glorias", "price": 35, "cost": 8, "stock": 260, "status": "active"},
    {"id": 10, "name": "طقم رموش مجموعة الصيف", "category": "رموش", "store": "glorias", "price": 120, "cost": 34, "stock": 130, "status": "active"},
    {"id": 11, "name": "رموش طبيعية ناعمة", "category": "رموش", "store": "glorias", "price": 55, "cost": 13, "stock": 0, "status": "active"},
    {"id": 12, "name": "ملقط رموش ذهبي", "category": "أدوات", "store": "glorias", "price": 39, "cost": 9, "stock": 900, "status": "active"},
]

_FIRST = ["نورة", "خالد", "ريم", "عبدالله", "هند", "فهد", "سارة", "محمد", "لمى", "تركي", "جود", "عبير",
          "ياسر", "منيرة", "أمل", "سلطان", "رهف", "ماجد", "دانة", "بندر", "غادة", "نايف", "شهد", "راكان"]
_LAST = ["السالم", "العتيبي", "الشهري", "القحطاني", "الدوسري", "المطيري", "الغامدي", "الزهراني",
         "الحربي", "العنزي", "الشمري", "المالكي", "البقمي", "السبيعي", "الرشيدي", "الجهني"]
# المدينة ووزنها في الطلبات
_CITIES = [("الرياض", 34), ("جدة", 20), ("الدمام", 10), ("مكة", 9), ("المدينة", 7), ("الخبر", 6),
           ("أبها", 5), ("تبوك", 4), ("القصيم", 5)]
_PAYMENTS = [("مدى", 38), ("Apple Pay", 24), ("فيزا", 14), ("تمارا", 14), ("الدفع عند الاستلام", 10)]
# ساعات الطلب: ذروة بالليل
_HOURS = [(h, w) for h, w in zip(range(24), [4, 2, 1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 7, 7, 6, 6, 7, 8, 9, 11, 13, 15, 14, 9])]
_SOURCES = [("سناب شات", 30), ("تيك توك", 22), ("انستقرام", 14), ("قوقل", 10), ("مباشر", 16)]
# كوبونات كل متجر: الكود -> (نسبة الخصم، كود مؤثر؟)
COUPONS = {
    "smooth": {"WELCOME10": (0.10, False), "SMOOTH15": (0.15, False), "VIP20": (0.20, False), "NOURA10": (0.10, True)},
    "glorias": {"WELCOME10": (0.10, False), "LASH15": (0.15, False), "GLOW20": (0.20, False), "RAWAN15": (0.15, True)},
}
_CARRIER_W = [("سمسا", 40), ("أرامكس", 20), ("سبل", 25), ("ريدبوكس", 15)]

# الحالة -> (صنف اللون، الأيقونة)
STATUSES = {
    "جديد": ("info", "spark"),
    "قيد التجهيز": ("warn", "box"),
    "تم الشحن": ("info", "truck"),
    "تم التسليم": ("ok", "check"),
    "ملغي": ("danger", "x"),
}
STATUS_CLASS = {k: v[0] for k, v in STATUSES.items()}


def _weighted(rnd, pairs):
    return rnd.choices([p[0] for p in pairs], weights=[p[1] for p in pairs])[0]


def _status_for(rnd, days_ago, payment):
    # الدفع عند الاستلام إلغاؤه أعلى
    if rnd.random() < (0.16 if payment == "الدفع عند الاستلام" else 0.04):
        return "ملغي"
    if 3 <= days_ago <= 5 and rnd.random() < 0.07:
        return "قيد التجهيز"  # طلبات متأخرة في التجهيز
    if days_ago == 0:
        return rnd.choice(["جديد", "جديد", "قيد التجهيز"])
    if days_ago <= 2:
        return rnd.choice(["قيد التجهيز", "تم الشحن", "تم الشحن"])
    if days_ago <= 5:
        return rnd.choice(["تم الشحن", "تم التسليم", "تم التسليم"])
    return "تم التسليم"


def enrich(o):
    """يحسب الضريبة والشحن والرسوم والربح لطلب واحد."""
    gross = o["total"]
    o["vat"] = finance.vat_of(gross)
    o["net"] = gross - o["vat"]
    o["merch_ex_vat"] = finance.ex_vat(o["subtotal"] - o["discount"])
    o["ship_ex_vat"] = finance.ex_vat(o["shipping"])
    o["cogs"] = sum(l["qty"] * l["cost"] for l in o["lines"])
    o["ship_cost"] = finance.carrier_cost_for(o["city"], o["carrier"])
    o["pay_fee"] = finance.payment_fee(o["payment"], gross)
    o["profit"] = o["net"] - o["cogs"] - o["ship_cost"] - o["pay_fee"]
    return o


def _build_orders():
    rnd = random.Random(11)
    today = date.today()
    pools = {"smooth": [], "glorias": []}  # عملاء سابقين لكل متجر
    base = {"smooth": 11, "glorias": 14}
    orders = []
    seq = 100000
    for i in range(HISTORY_DAYS):
        d = today - timedelta(days=HISTORY_DAYS - 1 - i)
        days_ago = HISTORY_DAYS - 1 - i
        growth = 1 + i / HISTORY_DAYS * 0.45
        boost = 1.3 if d.weekday() in (3, 4) else 1.0  # الخميس والجمعة
        for store, n in base.items():
            count = max(1, round(n * growth * boost * rnd.uniform(0.75, 1.25)))
            catalog = [p for p in PRODUCTS if p["store"] == store]
            for _ in range(count):
                seq += 1
                pool = pools[store]
                is_new = not (pool and rnd.random() < 0.38)
                if not is_new:
                    cust = rnd.choice(pool)
                else:
                    cust = {"id": f"{store[0]}{len(pool) + 1}",
                            "name": f"{rnd.choice(_FIRST)} {rnd.choice(_LAST)}",
                            "city": _weighted(rnd, _CITIES)}
                    pool.append(cust)
                lines = []
                for p in rnd.sample(catalog, rnd.choices([1, 2, 3], weights=[55, 32, 13])[0]):
                    lines.append({"product_id": p["id"], "name": p["name"], "qty": rnd.choices([1, 2, 3], weights=[70, 22, 8])[0],
                                  "price": p["price"], "cost": p["cost"]})
                subtotal = sum(l["qty"] * l["price"] for l in lines)
                coupon = None
                codes = COUPONS[store]
                if rnd.random() < 0.24:
                    coupon = rnd.choice([c for c in codes if c != "WELCOME10"] + (["WELCOME10"] * 2 if is_new else []))
                discount = round(subtotal * codes[coupon][0]) if coupon else 0
                if coupon and codes[coupon][1]:
                    source = "مؤثرين"
                else:
                    source = _weighted(rnd, _SOURCES)
                payment = _weighted(rnd, _PAYMENTS)
                carrier = _weighted(rnd, _CARRIER_W)
                lo, hi = finance.CARRIERS[carrier]["days"]
                delivery_days = rnd.randint(lo, hi)
                shipping = finance.shipping_charged(store, subtotal - discount)
                orders.append(enrich({
                    "id": str(seq),
                    "store": store,
                    "customer_id": cust["id"],
                    "customer": cust["name"],
                    "city": cust["city"],
                    "date": d.isoformat(),
                    "payment": payment,
                    "hour": _weighted(rnd, _HOURS),
                    "source": source,
                    "coupon": coupon,
                    "carrier": carrier,
                    "delivery_days": delivery_days,
                    "lines": lines,
                    "qty": sum(l["qty"] for l in lines),
                    "subtotal": subtotal,
                    "discount": discount,
                    "shipping": shipping,
                    "total": subtotal - discount + shipping,
                    "status": _status_for(rnd, days_ago, payment),
                }))
    orders.reverse()  # الأحدث أولاً
    return orders


ALL_ORDERS = _build_orders()
# الطلبات اللي بتظهر في صفحة الطلبات: آخر 60 لكل متجر
ORDERS = [o for o in ALL_ORDERS if o["store"] == "smooth"][:60] + [o for o in ALL_ORDERS if o["store"] == "glorias"][:60]
ORDERS.sort(key=lambda o: o["id"], reverse=True)

# المباع لكل منتج من كل الطلبات غير الملغية
_sold = defaultdict(int)
for _o in ALL_ORDERS:
    if _o["status"] != "ملغي":
        for _l in _o["lines"]:
            _sold[_l["product_id"]] += _l["qty"]
for _p in PRODUCTS:
    _p["sold"] = _sold[_p["id"]]


def _build_daily():
    """إجماليات يومية لكل متجر: المبيعات والطلبات والضريبة والشحن والربح."""
    rows = {}
    for i in range(HISTORY_DAYS):
        d = (date.today() - timedelta(days=HISTORY_DAYS - 1 - i)).isoformat()
        row = {"date": d}
        for s in ("smooth", "glorias"):
            for k in ("", "_orders", "_vat", "_ship_rev", "_ship_cost", "_profit"):
                row[s + k] = 0
        rows[d] = row
    for o in ALL_ORDERS:
        if o["status"] == "ملغي":
            continue
        r, s = rows[o["date"]], o["store"]
        r[s] += o["total"]
        r[s + "_orders"] += 1
        r[s + "_vat"] += o["vat"]
        r[s + "_ship_rev"] += o["ship_ex_vat"]
        r[s + "_ship_cost"] += o["ship_cost"]
        r[s + "_profit"] += o["profit"]
    out = list(rows.values())
    for r in out:
        for k, v in r.items():
            if isinstance(v, float):
                r[k] = round(v)
    return out


DAILY = _build_daily()

# العائد المستهدف لكل قناة (الإيراد ÷ المصروف) عشان البيانات التجريبية تبان واقعية
_TARGET_ROAS = {"سناب شات": 4.2, "تيك توك": 5.6, "انستقرام": 2.6, "قوقل": 6.3, "مؤثرين": 2.1}


def _build_ad_spend():
    """مصروف الإعلانات اليومي: {(تاريخ، متجر، قناة): مبلغ}."""
    rnd = random.Random(5)
    revenue = defaultdict(float)
    for o in ALL_ORDERS:
        if o["status"] != "ملغي" and o["source"] in _TARGET_ROAS:
            revenue[(o["date"], o["store"], o["source"])] += o["total"]
    spend = {}
    for i in range(HISTORY_DAYS):
        d = (date.today() - timedelta(days=HISTORY_DAYS - 1 - i)).isoformat()
        for store in ("smooth", "glorias"):
            for ch, roas in _TARGET_ROAS.items():
                rev = revenue.get((d, store, ch), 0)
                spend[(d, store, ch)] = round(max(rev, 150) / roas * rnd.uniform(0.8, 1.2))
    return spend


AD_SPEND = _build_ad_spend()


def for_store(items, store):
    """يرجّع العناصر الخاصة بالمتجر، أو كلها لو المتجر 'all'."""
    if store == "all":
        return list(items)
    return [i for i in items if i["store"] == store]


def low_stock(products, threshold=10):
    return [p for p in products if p["stock"] <= threshold]


def status_counts(orders):
    counts = {s: 0 for s in STATUSES}
    for o in orders:
        counts[o["status"]] += 1
    return counts
