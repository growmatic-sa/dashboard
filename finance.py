"""افتراضات الحسابات المالية. عدّل القيم هنا وكل التقارير بتتحسب على أساسها.

كل المبالغ بالريال السعودي.
"""

# ضريبة القيمة المضافة في السعودية
VAT_RATE = 0.15
# أسعار سلة بتظهر للعميل شاملة الضريبة عادةً
PRICES_INCLUDE_VAT = True

# الشحن اللي بيدفعه العميل (شامل الضريبة)
SHIPPING_FEE = {"smooth": 25, "glorias": 20}
FREE_SHIPPING_OVER = {"smooth": 250, "glorias": 150}

# تكلفة الشحن الفعلية على المتجر لكل طلب (بدون ضريبة) حسب المدينة
CARRIER_COST = {"الرياض": 16, "جدة": 19, "الدمام": 19, "الخبر": 19, "مكة": 21, "المدينة": 21}
CARRIER_COST_DEFAULT = 24

# رسوم بوابات الدفع: نسبة من المبلغ + مبلغ ثابت لكل عملية
PAYMENT_FEES = {
    "مدى": (0.010, 0),
    "فيزا": (0.025, 0),
    "Apple Pay": (0.020, 0),
    "تمارا": (0.065, 0),
    "الدفع عند الاستلام": (0.0, 12),
}


def vat_of(gross):
    """قيمة الضريبة داخل مبلغ شامل الضريبة."""
    if PRICES_INCLUDE_VAT:
        return gross * VAT_RATE / (1 + VAT_RATE)
    return gross * VAT_RATE


def ex_vat(gross):
    return gross - vat_of(gross) if PRICES_INCLUDE_VAT else gross


def shipping_charged(store, merch_total):
    return 0 if merch_total >= FREE_SHIPPING_OVER[store] else SHIPPING_FEE[store]


def carrier_cost(city):
    return CARRIER_COST.get(city, CARRIER_COST_DEFAULT)


def payment_fee(method, amount):
    pct, flat = PAYMENT_FEES.get(method, (0, 0))
    return amount * pct + flat


# ---------- شركات الشحن ----------
# factor: مضاعف على تكلفة المدينة · days: مدى أيام التوصيل المعتاد
CARRIERS = {
    "سمسا": {"factor": 1.00, "days": (1, 4)},
    "أرامكس": {"factor": 1.12, "days": (2, 5)},
    "سبل": {"factor": 0.85, "days": (2, 8)},
    "ريدبوكس": {"factor": 0.78, "days": (1, 4)},
}
# أكتر من كده يعتبر الطلب متأخر
DELIVERY_SLA_DAYS = 4
# طلب "قيد التجهيز" أكتر من كده يعتبر متأخر في التجهيز
PROCESSING_SLA_DAYS = 2


def carrier_cost_for(city, carrier):
    return round(carrier_cost(city) * CARRIERS.get(carrier, {"factor": 1})["factor"], 2)


# ---------- المخزون ----------
LEAD_TIME_DAYS = 7       # مدة وصول البضاعة من المورد
SAFETY_DAYS = 5          # مخزون أمان إضافي
TARGET_COVER_DAYS = 30   # الكمية المقترحة تكفي كام يوم بعد وصولها

# ---------- التسويق ----------
AD_CHANNELS = ["سناب شات", "تيك توك", "انستقرام", "قوقل", "مؤثرين"]
ORGANIC = "مباشر"

# ---------- محاكي القرارات ----------
# مرونة الطلب السعرية: رفع السعر 10% يقلل الكمية حوالي 13%
PRICE_ELASTICITY = -1.3
# العائد الإضافي من زيادة الإعلانات أقل من المتوسط الحالي (تناقص العائد)
AD_MARGINAL_FACTOR = 0.65
