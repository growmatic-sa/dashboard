"""بيانات تجريبية للعرض فقط. تُستبدل ببيانات سلة الحقيقية في المرحلة الجاية."""

import random
from datetime import date, timedelta

PRODUCTS = [
    {"id": 1, "name": "سيروم فيتامين C", "category": "العناية بالبشرة", "store": "smooth", "price": 189, "stock": 42, "sold": 128, "status": "active"},
    {"id": 2, "name": "كريم ترطيب يومي", "category": "العناية بالبشرة", "store": "smooth", "price": 145, "stock": 6, "sold": 97, "status": "active"},
    {"id": 3, "name": "ماسك طين للبشرة الدهنية", "category": "ماسكات", "store": "smooth", "price": 75, "stock": 0, "sold": 64, "status": "active"},
    {"id": 4, "name": "غسول لطيف يومي", "category": "منظفات", "store": "smooth", "price": 95, "stock": 18, "sold": 52, "status": "active"},
    {"id": 5, "name": "واقي شمس SPF 50", "category": "العناية بالبشرة", "store": "smooth", "price": 120, "stock": 31, "sold": 88, "status": "active"},
    {"id": 6, "name": "تونر الورد", "category": "منظفات", "store": "smooth", "price": 85, "stock": 9, "sold": 45, "status": "draft"},
    {"id": 7, "name": "رموش صناعية كثيفة", "category": "رموش", "store": "glorias", "price": 59, "stock": 3, "sold": 210, "status": "active"},
    {"id": 8, "name": "غراء رموش شفاف", "category": "أدوات", "store": "glorias", "price": 49, "stock": 25, "sold": 176, "status": "active"},
    {"id": 9, "name": "مزيل غراء آمن", "category": "أدوات", "store": "glorias", "price": 35, "stock": 14, "sold": 88, "status": "active"},
    {"id": 10, "name": "طقم رموش مجموعة الصيف", "category": "رموش", "store": "glorias", "price": 120, "stock": 9, "sold": 41, "status": "draft"},
    {"id": 11, "name": "رموش طبيعية ناعمة", "category": "رموش", "store": "glorias", "price": 55, "stock": 0, "sold": 133, "status": "active"},
    {"id": 12, "name": "ملقط رموش ذهبي", "category": "أدوات", "store": "glorias", "price": 39, "stock": 47, "sold": 62, "status": "active"},
]

_CUSTOMERS = [
    "نورة السالم", "خالد العتيبي", "ريم الشهري", "عبدالله القحطاني", "هند الدوسري",
    "فهد المطيري", "سارة الغامدي", "محمد الزهراني", "لمى الحربي", "تركي العنزي",
    "جود الشمري", "عبير المالكي", "ياسر البقمي", "منيرة السبيعي",
]
_CITIES = ["الرياض", "جدة", "الدمام", "مكة", "المدينة", "الخبر", "أبها"]

# الحالة -> (صنف اللون، الأيقونة)
STATUSES = {
    "جديد": ("info", "spark"),
    "قيد التجهيز": ("warn", "box"),
    "تم الشحن": ("info", "truck"),
    "تم التسليم": ("ok", "check"),
    "ملغي": ("danger", "x"),
}
STATUS_CLASS = {k: v[0] for k, v in STATUSES.items()}


def _build_orders():
    rnd = random.Random(7)
    today = date.today()
    weights = [("تم التسليم", 46), ("تم الشحن", 18), ("قيد التجهيز", 14), ("جديد", 14), ("ملغي", 8)]
    statuses = [s for s, w in weights for _ in range(w)]
    orders = []
    for n in range(28):
        store = "smooth" if rnd.random() < 0.55 else "glorias"
        pool = [p for p in PRODUCTS if p["store"] == store]
        lines = []
        for p in rnd.sample(pool, rnd.randint(1, 3)):
            qty = rnd.randint(1, 3)
            lines.append({"name": p["name"], "qty": qty, "price": p["price"]})
        days_ago = n // 3
        status = "جديد" if days_ago == 0 and n % 2 == 0 else rnd.choice(statuses)
        orders.append({
            "id": str(1060 - n),
            "customer": rnd.choice(_CUSTOMERS),
            "city": rnd.choice(_CITIES),
            "store": store,
            "lines": lines,
            "qty": sum(l["qty"] for l in lines),
            "total": sum(l["qty"] * l["price"] for l in lines),
            "status": status,
            "date": (today - timedelta(days=days_ago)).isoformat(),
            "payment": rnd.choice(["مدى", "Apple Pay", "فيزا", "تمارا", "الدفع عند الاستلام"]),
        })
    return orders


ORDERS = _build_orders()


def _build_daily(days=90):
    """مبيعات وطلبات يومية لكل متجر لآخر 90 يوم، بنمط أسبوعي ونمو بسيط."""
    rnd = random.Random(42)
    today = date.today()
    base = {"smooth": (2300, 13), "glorias": (1500, 16)}
    out = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        weekend = d.weekday() in (3, 4)  # الخميس والجمعة أعلى
        growth = 1 + i / days * 0.35
        row = {"date": d.isoformat()}
        for store, (rev, cnt) in base.items():
            noise = rnd.uniform(0.78, 1.22)
            boost = 1.3 if weekend else 1.0
            row[store] = round(rev * growth * noise * boost)
            row[store + "_orders"] = max(1, round(cnt * growth * noise * boost))
        out.append(row)
    return out


DAILY = _build_daily()


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
