"""بيانات تجريبية للعرض فقط. تُستبدل ببيانات سلة الحقيقية في المرحلة الجاية."""

PRODUCTS = [
    {"id": 1, "name": "سيروم فيتامين C", "store": "smooth", "price": 189, "stock": 42, "sold": 128, "status": "active"},
    {"id": 2, "name": "كريم ترطيب يومي", "store": "smooth", "price": 145, "stock": 6, "sold": 97, "status": "active"},
    {"id": 3, "name": "ماسك طين للبشرة الدهنية", "store": "smooth", "price": 75, "stock": 0, "sold": 64, "status": "active"},
    {"id": 4, "name": "غسول لطيف يومي", "store": "smooth", "price": 95, "stock": 18, "sold": 52, "status": "active"},
    {"id": 5, "name": "رموش صناعية كثيفة", "store": "glorias", "price": 59, "stock": 3, "sold": 210, "status": "active"},
    {"id": 6, "name": "غراء رموش شفاف", "store": "glorias", "price": 49, "stock": 25, "sold": 176, "status": "active"},
    {"id": 7, "name": "مزيل غراء آمن", "store": "glorias", "price": 35, "stock": 14, "sold": 88, "status": "active"},
    {"id": 8, "name": "طقم رموش مجموعة الصيف", "store": "glorias", "price": 120, "stock": 9, "sold": 41, "status": "draft"},
]

ORDERS = [
    {"id": "1042", "customer": "نورة السالم", "store": "smooth", "total": 334, "items": 2, "status": "جديد", "date": "10 أكتوبر"},
    {"id": "1041", "customer": "خالد العتيبي", "store": "glorias", "total": 118, "items": 2, "status": "قيد التجهيز", "date": "10 أكتوبر"},
    {"id": "1040", "customer": "ريم الشهري", "store": "smooth", "total": 189, "items": 1, "status": "تم الشحن", "date": "9 أكتوبر"},
    {"id": "1039", "customer": "عبدالله القحطاني", "store": "glorias", "total": 49, "items": 1, "status": "تم التسليم", "date": "9 أكتوبر"},
    {"id": "1038", "customer": "هند الدوسري", "store": "smooth", "total": 240, "items": 3, "status": "تم التسليم", "date": "8 أكتوبر"},
    {"id": "1037", "customer": "فهد المطيري", "store": "glorias", "total": 179, "items": 3, "status": "ملغي", "date": "8 أكتوبر"},
]

# مبيعات آخر 7 أيام (بالريال)
SALES_WEEK = [
    {"day": "السبت", "value": 2100},
    {"day": "الأحد", "value": 2800},
    {"day": "الاثنين", "value": 2450},
    {"day": "الثلاثاء", "value": 3400},
    {"day": "الأربعاء", "value": 3050},
    {"day": "الخميس", "value": 4100},
    {"day": "الجمعة", "value": 3720},
]

STATUS_CLASS = {
    "جديد": "info",
    "قيد التجهيز": "warn",
    "تم الشحن": "info",
    "تم التسليم": "ok",
    "ملغي": "danger",
}


def for_store(items, store):
    """يرجّع العناصر الخاصة بالمتجر، أو كلها لو المستخدم على 'all'."""
    if store == "all":
        return list(items)
    return [i for i in items if i["store"] == store]


def low_stock(products, threshold=10):
    return [p for p in products if p["stock"] <= threshold]
