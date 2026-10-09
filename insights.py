"""محرّك الرؤى: بيحوّل التحليلات لتوصيات مرتبة حسب الأهمية والأثر بالريال.

الأثر تقديري وشهري، ومكتوب جنب كل توصية الافتراض اللي اتبنى عليه.
"""

from collections import defaultdict
from datetime import date, timedelta

import analytics as an
import finance
import sample_data as sample

SEVERITY = {
    "critical": {"label": "عاجل", "order": 0, "icon": "alert"},
    "warning": {"label": "انتبه", "order": 1, "icon": "alert"},
    "opportunity": {"label": "فرصة", "order": 2, "icon": "spark"},
    "info": {"label": "معلومة", "order": 3, "icon": "chart"},
}

_cache = {}


def _store_name(s):
    return {"smooth": "سموذ", "glorias": "قلوريز"}.get(s, "كل المتاجر")


def build(store, target=None):
    key = (store, date.today().isoformat(), target)
    if key not in _cache:
        _cache.clear()
        _cache[key] = _build(store, target)
    return _cache[key]


def _build(store, target):
    out = []
    add = lambda **kw: out.append(kw)
    stores = ["smooth", "glorias"] if store == "all" else [store]

    # 1) منتجات نافدة بتتباع
    plan = an.inventory_plan(store)
    for p in [p for p in plan if p["state"] == "out"]:
        add(severity="critical", area="المخزون", title=f"«{p['name']}» نافد وعليه طلب",
            body=f"بيتباع منه حوالي {p['velocity']:.1f} قطعة يومياً. اطلب {p['reorder_qty']} قطعة "
                 f"(تكلفة تقريبية {p['reorder_cash']:,.0f} ر.س).",
            impact=p["lost_per_day"] * 30, impact_note="مبيعات ضايعة شهرياً لو فضل نافد",
            action=("خطة المخزون", "inventory"))

    # 2) لازم تطلب دلوقتي
    reorder = [p for p in plan if p["state"] == "reorder"]
    if reorder:
        cash = sum(p["reorder_cash"] for p in reorder)
        names = "، ".join(p["name"] for p in reorder[:3])
        add(severity="warning", area="المخزون", title=f"{len(reorder)} منتج وصل لحد إعادة الطلب",
            body=f"{names}{' وغيرها' if len(reorder) > 3 else ''}. المخزون مش هيكفي لحد وصول الشحنة الجديدة "
                 f"({finance.LEAD_TIME_DAYS} أيام). السيولة المطلوبة حوالي {cash:,.0f} ر.س.",
            impact=None, action=("خطة المخزون", "inventory"))

    # 3) مخزون راكد
    over = [p for p in plan if p["state"] == "over"]
    if over:
        tied = sum(p["stock"] * p["cost"] for p in over)
        add(severity="opportunity", area="المخزون", title=f"{tied:,.0f} ر.س مجمّدة في مخزون بطيء",
            body=f"{'، '.join(p['name'] for p in over[:3])} تكفي أكتر من 90 يوم. عرض أو باقة هيحرّر السيولة.",
            impact=None, action=("خطة المخزون", "inventory"))

    # 4) طلبات متأخرة في التجهيز
    late = an.delayed_orders(store)
    if late:
        add(severity="critical", area="العمليات", title=f"{len(late)} طلب متأخر في التجهيز",
            body=f"أقدم طلب عمره {late[0]['age']} أيام. التأخير بيرفع الإلغاء والتقييمات السلبية.",
            impact=sum(o["total"] for o in late), impact_note="قيمة الطلبات المعرّضة للإلغاء",
            action=("الطلبات", "orders"))

    # 5) حد الشحن المجاني
    for s in stores:
        orders = an.live(s, 30)
        cur = finance.FREE_SHIPPING_OVER[s]
        fee_ex = finance.ex_vat(finance.SHIPPING_FEE[s])
        new = cur + 50
        affected = [o for o in orders if cur <= o["subtotal"] - o["discount"] < new]
        gain = len(affected) * fee_ex
        ship_net = sum(o["ship_ex_vat"] - o["ship_cost"] for o in orders)
        if gain > 500:
            add(severity="opportunity", area="الشحن", title=f"رفع حد الشحن المجاني في {_store_name(s)} من {cur} إلى {new} ر.س",
                body=f"{len(affected)} طلب الشهر ده كان بين {cur} و{new} ر.س وأخد شحن مجاني. "
                     f"صافي الشحن حالياً {ship_net:,.0f} ر.س. جرّبه في المحاكي قبل التطبيق.",
                impact=gain, impact_note="حد أقصى، بافتراض نفس سلوك الشراء",
                action=("جرّب في المحاكي", "simulator"))

    # 6) القنوات الإعلانية
    m = an.marketing(store, 30)
    ch = [c for c in m["channels"] if c["roas"]]
    if len(ch) >= 2:
        best, worst = ch[0], ch[-1]
        moved = worst["spend"] * 0.3
        rev_gain = moved * (best["roas"] * finance.AD_MARGINAL_FACTOR - worst["roas"])
        margin = m["profit_before_ads"] / m["revenue"] if m["revenue"] else 0
        if rev_gain > 0:
            add(severity="opportunity", area="التسويق", title=f"انقل 30% من ميزانية {worst['name']} إلى {best['name']}",
                body=f"العائد في {best['name']} {best['roas']:.1f}× مقابل {worst['roas']:.1f}× في {worst['name']}. "
                     f"نقل {moved:,.0f} ر.س شهرياً متوقع يزوّد المبيعات حوالي {rev_gain:,.0f} ر.س.",
                impact=rev_gain * margin, impact_note=f"ربح إضافي بافتراض تناقص العائد {round(finance.AD_MARGINAL_FACTOR * 100)}%",
                action=("التسويق", "marketing"))
        for c in ch:
            if c["net"] < 0:
                add(severity="warning", area="التسويق", title=f"قناة {c['name']} بتخسر بعد مصروف الإعلان",
                    body=f"صرفت {c['spend']:,.0f} ر.س وجابت ربح {c['profit']:,.0f} ر.س قبل الإعلان. "
                         f"راجع الاستهداف أو قلّل الميزانية.",
                    impact=-c["net"], impact_note="خسارة شهرية بعد الإعلان", action=("التسويق", "marketing"))

    # 7) الكوبونات
    cps = an.coupons(store, 60)
    if cps:
        avg = sum(c["profit"] for c in cps) / sum(c["uses"] for c in cps)
        for c in cps:
            if c["uses"] >= 20 and c["profit_per_order"] < avg * 0.7:
                add(severity="warning", area="التسويق", title=f"كوبون {c['code']} أضعف من المتوسط",
                    body=f"ربح الطلب {c['profit_per_order']:,.0f} ر.س مقابل {avg:,.0f} ر.س لباقي الكوبونات، "
                         f"وخصمه {c['rate']:.0f}%. فكّر تخفّض النسبة أو تحط حد أدنى للطلب.",
                    impact=(avg - c["profit_per_order"]) * c["uses"] / 2, impact_note="الفرق شهرياً",
                    action=("الكوبونات", "marketing"))

    # 8) عملاء معرّضون للفقد
    custs = an.customers(store)
    risk = [c for c in custs if c["segment"] == "at_risk"]
    if risk:
        avg_order = sum(c["spent"] for c in risk) / sum(c["orders"] for c in risk)
        add(severity="opportunity", area="العملاء", title=f"{len(risk)} عميل متكرر بطّل يشتري",
            body=f"اشتروا قبل كده بإجمالي {sum(c['spent'] for c in risk):,.0f} ر.س، وآخر طلب لهم من أكتر من 45 يوم. "
                 f"حملة استرجاع هترجّع جزء منهم.",
            impact=len(risk) * 0.2 * avg_order, impact_note="لو رجع 20% منهم بطلب واحد",
            action=("قائمة العملاء", "customers"))

    # 9) الإلغاء في الدفع عند الاستلام
    by_pay = defaultdict(lambda: [0, 0])
    for o in [o for o in sample.for_store(sample.ALL_ORDERS, store) if o["date"] >= (date.today() - timedelta(days=60)).isoformat()]:
        by_pay[o["payment"] == "الدفع عند الاستلام"][0] += 1
        by_pay[o["payment"] == "الدفع عند الاستلام"][1] += o["status"] == "ملغي"
    cod, other = by_pay[True], by_pay[False]
    if cod[0] and other[0]:
        cod_rate, other_rate = cod[1] / cod[0] * 100, other[1] / other[0] * 100
        cod_done = [o for o in sample.for_store(sample.ALL_ORDERS, store) if o["payment"] == "الدفع عند الاستلام" and o["status"] != "ملغي"]
        avg_profit = sum(o["profit"] for o in cod_done) / len(cod_done) if cod_done else 0
        # الإلغاء الزيادة عن المعدل الطبيعي، مقسوم على شهرين
        excess_profit = max(0, cod[1] - cod[0] * other_rate / 100) / 2 * avg_profit
        if cod_rate > other_rate * 2:
            add(severity="warning", area="العمليات", title=f"إلغاء الدفع عند الاستلام {cod_rate:.0f}%",
                body=f"مقابل {other_rate:.0f}% لباقي طرق الدفع. رسوم بسيطة على الدفع عند الاستلام أو تأكيد الطلب بالواتساب بيقلل الإلغاء.",
                impact=excess_profit, impact_note="ربح ضايع شهرياً من الإلغاء الزيادة",
                action=("التقارير", "reports"))

    # 10) شركات الشحن
    cars = an.carriers(store)
    slow = [c for c in cars if c["late_rate"] > 25 and c["orders"] >= 30]
    fast = sorted([c for c in cars if c["late_rate"] < 15], key=lambda c: c["avg_cost"])
    for c in slow:
        alt = fast[0] if fast else None
        if alt:
            add(severity="warning", area="الشحن", title=f"{c['name']} متأخرة في {c['late_rate']:.0f}% من الطلبات",
                body=f"متوسط التوصيل {c['avg_days']:.1f} يوم. {alt['name']} أسرع ({alt['avg_days']:.1f} يوم) "
                     f"وتكلفتها {alt['avg_cost']:.1f} ر.س مقابل {c['avg_cost']:.1f} ر.س.",
                impact=None, action=("شركات الشحن", "reports"))

    # 11) باقات من منتجات بتتشرى مع بعض
    pairs = an.basket_pairs(store)
    if pairs and pairs[0]["lift"] > 1.2:
        p = pairs[0]
        add(severity="opportunity", area="المنتجات", title=f"باقة «{p['a']}» + «{p['b']}»",
            body=f"اتشروا مع بعض {p['count']} مرة، وده {p['lift']:.1f}× أكتر من الصدفة. "
                 f"باقة بخصم بسيط هترفع متوسط قيمة الطلب.",
            impact=None, action=("تحليل المنتجات", "insights"))

    # 12) الهدف الشهري
    if target:
        g = an.month_progress(store, target)
        if g["projected_pct"] < 97:
            add(severity="warning", area="الأهداف", title=f"متوقع نوصل {g['projected_pct']:.0f}% من هدف {g['month_label']}",
                body=f"محتاجين {g['required_daily']:,.0f} ر.س يومياً لباقي الشهر، والمعدل الحالي {g['run_rate']:,.0f} ر.س.",
                impact=target - g["projected"], impact_note="الفجوة المتوقعة عن الهدف", action=("الأهداف", "goals"))
        else:
            add(severity="info", area="الأهداف", title=f"على الطريق لتحقيق هدف {g['month_label']}",
                body=f"التوقع {g['projected']:,.0f} ر.س ({g['projected_pct']:.0f}% من الهدف).",
                impact=None, action=("الأهداف", "goals"))

    # 13) وقت الذروة
    h = an.heatmap(store)
    add(severity="info", area="التسويق", title=f"الذروة يوم {h['best']['day']} من {h['best']['slot']}",
        body="جدول الإعلانات ورسائل العروض قبل الذروة بساعة، ورتّب فريق خدمة العملاء على الأوقات دي.",
        impact=None, action=("خريطة الأوقات", "marketing"))

    out.sort(key=lambda i: (SEVERITY[i["severity"]]["order"], -(i.get("impact") or 0)))
    return out


def morning_brief(store):
    """موجز امبارح مقارنة بنفس اليوم الأسبوع اللي فات."""
    t = date.today()
    y, ly = (t - timedelta(days=1)).isoformat(), (t - timedelta(days=8)).isoformat()
    orders = sample.for_store(sample.ALL_ORDERS, store)
    day = [o for o in orders if o["date"] == y and o["status"] != "ملغي"]
    prev = [o for o in orders if o["date"] == ly and o["status"] != "ملغي"]
    sales, psales = sum(o["total"] for o in day), sum(o["total"] for o in prev)
    top = defaultdict(int)
    for o in day:
        for l in o["lines"]:
            top[l["name"]] += l["qty"]
    first_ids = set()
    seen = set()
    for o in sorted(orders, key=lambda o: o["date"]):
        if o["status"] != "ملغي" and o["customer_id"] not in seen:
            seen.add(o["customer_id"])
            if o["date"] == y:
                first_ids.add(o["customer_id"])
    return {
        "sales": sales,
        "change": (sales - psales) / psales * 100 if psales else None,
        "orders": len(day),
        "profit": sum(o["profit"] for o in day),
        "new_customers": len(first_ids),
        "top": max(top.items(), key=lambda kv: kv[1]) if top else None,
    }
