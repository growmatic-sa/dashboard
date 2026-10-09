import os
import secrets
from functools import wraps

from markupsafe import Markup
from flask import Flask, Response, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import envfile
envfile.load()

import db  # noqa: E402  (يجب أن يأتي بعد تحميل .env)
import analytics as an
import export
import insights as ins
import finance
import reports
import sample_data as sample
from brands import PANEL, SERIES, brand_for
from permissions import PAGES, ROLES, STORES, can_access_page, can_edit

PRODUCTION = os.environ.get("APP_ENV") == "production"

app = Flask(__name__)
secret = os.environ.get("SECRET_KEY")
if PRODUCTION and (not secret or len(secret) < 32):
    # بدون مفتاح ثابت كل عملية تشغيل هيكون لها مفتاح مختلف والمستخدمين هيخرجوا من حساباتهم
    raise SystemExit("SECRET_KEY لازم يكون مضبوط (32 حرف على الأقل) في بيئة الإنتاج.")
app.config["SECRET_KEY"] = secret or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = PRODUCTION or os.environ.get("COOKIE_SECURE", "0") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 12  # 12 ساعة

if PRODUCTION:
    # الاستضافة بتمرّر الطلبات عن طريق بروكسي، فناخد البروتوكول والـ IP الحقيقي منه
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db.init_app(app)
with app.app_context():
    if os.environ.get("OWNER_EMAIL"):
        db.seed_owner_if_empty()

# قفل مؤقت بعد محاولات دخول فاشلة
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if PRODUCTION:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp


@app.route("/healthz")
def healthz():
    return {"ok": True}


@app.template_filter("money")
def money_filter(v, digits=0):
    return f"{v:,.{digits}f}"


@app.template_filter("signed")
def signed_filter(v, digits=0):
    """رقم بإشارة سالب في مكانها الصحيح داخل النص العربي."""
    text = f"{'−' if v < 0 else ''}{abs(v):,.{digits}f}"
    return Markup('<bdi dir="ltr"{}>{}</bdi>').format(Markup(' class="neg"') if v < 0 else "", text)


@app.template_filter("pct")
def pct_filter(v):
    return f"{v:.1f}%"


# ---------- helpers ----------

def current_user():
    if "user_id" not in session:
        return None
    if "user" not in g:
        g.user = db.get_user_by_id(session["user_id"])
    return g.user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def page_required(page):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for("login"))
            if not can_access_page(user["role"], page):
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400, description="طلب غير صالح، حدّث الصفحة وحاول تاني.")


def selected_store(user):
    """المتجر المعروض حالياً. المستخدم المقيّد بمتجر يشوف متجره بس."""
    if user is None:
        return "all"
    if user["store"] != "all":
        return user["store"]
    requested = request.args.get("store")
    if requested in STORES:
        session["store"] = requested
    return session.get("store", "all")


@app.context_processor
def inject_globals():
    user = current_user()
    store = selected_store(user)
    if user is None or user["store"] == "all":
        store_options = list(STORES)
    else:
        store_options = [user["store"]]
    return {
        "brand": brand_for(store),
        "panel": PANEL,
        "store": store,
        "store_options": store_options,
        "brand_for": brand_for,
        "csrf_token": csrf_token,
        "current_user": user,
        "pages": PAGES,
        "role_names": ROLES,
        "store_names": STORES,
        "can_page": lambda page: bool(user) and can_access_page(user["role"], page),
        "alerts": alerts_for(user, store),
        "static_demo": app.config.get("STATIC_DEMO", False),
    }


def alerts_for(user, store):
    if user is None or not can_access_page(user["role"], "insights"):
        return []
    return [i for i in ins.build(store, goal_for(store)) if i["severity"] in ("critical", "warning")]


# ---------- auth ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        ip = request.remote_addr or ""
        if db.recent_failed_logins(email, ip, LOCKOUT_MINUTES) >= MAX_FAILED_LOGINS:
            db.log_action(None, "login_locked", f"محاولة أثناء القفل: {email} من {ip}")
            flash(f"محاولات كتير غلط. استنى {LOCKOUT_MINUTES} دقيقة وجرّب تاني.", "error")
            return render_template("login.html"), 429
        user = db.get_user_by_email(email)
        if user and user["active"] and check_password_hash(user["password_hash"], password):
            db.clear_failed_logins(email, ip)
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["csrf"] = secrets.token_hex(16)
            db.log_action(user["id"], "login", f"تسجيل دخول من {ip}")
            return redirect(url_for("index"))
        db.record_failed_login(email, ip)
        db.log_action(None, "login_failed", f"محاولة فاشلة: {email} من {ip}")
        flash("البريد أو كلمة المرور غير صحيحة.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    db.log_action(current_user()["id"], "logout", "تسجيل خروج")
    session.clear()
    return redirect(url_for("login"))


# ---------- pages ----------

@app.route("/")
@login_required
def index():
    user = current_user()
    # أول صفحة مسموحة للمستخدم
    for key in PAGES:
        if can_access_page(user["role"], key):
            return redirect(url_for("page", key=key))
    abort(403)


PAGE_TEMPLATES = {
    "dashboard": "pages/dashboard.html",
    "orders": "pages/orders.html",
    "products": "pages/products.html",
    "inventory": "pages/inventory.html",
    "reports": "pages/reports.html",
    "insights": "pages/insights.html",
    "customers": "pages/customers.html",
    "marketing": "pages/marketing.html",
    "goals": "pages/goals.html",
    "simulator": "pages/simulator.html",
    "settings": "pages/settings.html",
}


@app.route("/p/<key>")
@login_required
def page(key):
    if key not in PAGES:
        abort(404)
    user = current_user()
    if not can_access_page(user["role"], key):
        abort(403)
    template = PAGE_TEMPLATES.get(key, "page.html")
    ctx = build_page_context(key, selected_store(user))
    return render_template(template, key=key, title=PAGES[key]["label"], **ctx)


def month_key():
    return an.today().strftime("%Y-%m")


def goal_for(store):
    if store == "all":
        return sum(goal_for(s) for s in ("smooth", "glorias"))
    saved = db.get_goal(store, month_key())
    return saved if saved is not None else an.suggested_target(store)


def build_page_context(key, store):
    orders = sample.for_store(sample.ORDERS, store)
    products = sample.for_store(sample.PRODUCTS, store)
    low = sample.low_stock(products)
    if key == "dashboard":
        stores = ["smooth", "glorias"] if store == "all" else [store]
        plan = an.inventory_plan(store)
        needs = [p for p in plan if p["state"] in ("out", "reorder", "soon")]
        return {
            "goal": an.month_progress(store, goal_for(store)),
            "top_insights": [i for i in ins.build(store, goal_for(store)) if i["severity"] != "info"][:3],
            "severity": ins.SEVERITY,
            "dash_data": {
                "stores": [
                    {"key": s, "name": STORES[s], "color": SERIES[s]} for s in stores
                ],
                "daily": sample.DAILY,
            },
            "recent_orders": orders[:5],
            "low_stock": needs[:5],
            "low_count": len([p for p in plan if p["state"] in ("out", "reorder")]),
            "top_products": sorted(products, key=lambda p: p["sold"], reverse=True)[:5],
            "status_counts": sample.status_counts(orders),
            "statuses": sample.STATUSES,
            "orders_total": len(orders),
        }
    if key == "orders":
        return {
            "orders": orders,
            "statuses": sample.STATUSES,
            "status_counts": sample.status_counts(orders),
        }
    if key == "products":
        return {"products": products}
    if key == "reports":
        r = reports.build(request.args.get("kind", "month"), request.args.get("period"), store)
        stores = ["smooth", "glorias"] if store == "all" else [store]
        r["chart"] = {
            "stores": [{"key": s, "name": STORES[s], "color": SERIES[s]} for s in stores],
            "trend": r["trend"],
            "current": r["period"]["key"],
        }
        r["finance_vat"] = finance.VAT_RATE
        r["sla"] = finance.DELIVERY_SLA_DAYS
        return r
    if key == "settings":
        return {"finance": finance}
    if key == "inventory":
        plan = an.inventory_plan(store)
        return {
            "plan": plan,
            "counts": {st: len([p for p in plan if p["state"] == st]) for st in ("out", "reorder", "soon", "ok", "over")},
            "cash_needed": sum(p["reorder_cash"] for p in plan),
            "stock_value": sum(p["stock"] * p["cost"] for p in plan),
            "lead_time": finance.LEAD_TIME_DAYS,
            "cover_target": finance.TARGET_COVER_DAYS,
        }
    if key == "insights":
        return {
            "items": ins.build(store, goal_for(store)),
            "severity": ins.SEVERITY,
            "brief": ins.morning_brief(store),
            "abc": an.abc(store),
            "pairs": an.basket_pairs(store),
        }
    if key == "customers":
        custs = an.customers(store)
        return {
            "segments": an.segment_summary(custs),
            "cohorts": an.cohorts(store),
            "stats": an.repeat_stats(custs),
            "total_customers": len(custs),
            "top": sorted(custs, key=lambda c: c["spent"], reverse=True)[:10],
            "at_risk": sorted([c for c in custs if c["segment"] == "at_risk"], key=lambda c: c["spent"], reverse=True)[:10],
        }
    if key == "marketing":
        window = request.args.get("days", "30")
        window = int(window) if window in ("7", "30", "90") else 30
        return {
            "window": window,
            "mk": an.marketing(store, window),
            "coupons": an.coupons(store, window),
            "heat": an.heatmap(store, max(window, 30)),
        }
    if key == "goals":
        stores = ["smooth", "glorias"] if store == "all" else [store]
        return {
            "goal_rows": [
                {"store": s, "progress": an.month_progress(s, goal_for(s)), "history": an.monthly_history(s),
                 "suggested": an.suggested_target(s), "saved": db.get_goal(s, month_key()) is not None}
                for s in stores
            ],
            "total": an.month_progress(store, goal_for(store)) if store == "all" else None,
            "editable": can_edit(current_user()["role"], "goals"),
        }
    if key == "simulator":
        return {"sim": an.simulator_baseline(store), "sim_stores": ["smooth", "glorias"] if store == "all" else [store]}
    return {}


@app.route("/reports/export")
@page_required("reports")
def reports_export():
    user = current_user()
    store = selected_store(user)
    fmt = request.args.get("format", "xlsx")
    r = reports.build(request.args.get("kind", "month"), request.args.get("period"), store)
    label = STORES[store]
    filename = f"report-{store}-{r['kind']}-{r['period']['key']}"
    db.log_action(user["id"], "report_exported", f"تصدير {fmt}: {label} — {r['period']['label']}")
    if fmt == "csv":
        return Response(export.build_csv(r, STORES), mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename={filename}.csv"})
    data = export.build_xlsx(r, label, STORES, brand_for(store)["light"]["fill"])
    return Response(data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"})


@app.route("/goals", methods=["POST"])
@page_required("goals")
def goals_save():
    user = current_user()
    if not can_edit(user["role"], "goals"):
        abort(403)
    allowed = ["smooth", "glorias"] if user["store"] == "all" else [user["store"]]
    for s in allowed:
        raw = request.form.get(f"target_{s}", "").replace(",", "").strip()
        if not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            flash("اكتب الهدف أرقام بس.", "error")
            return redirect(url_for("page", key="goals"))
        if value <= 0 or value > 100_000_000:
            flash("قيمة الهدف غير منطقية.", "error")
            return redirect(url_for("page", key="goals"))
        db.set_goal(s, month_key(), value, user["id"])
        db.log_action(user["id"], "goal_set", f"هدف {STORES[s]} لشهر {month_key()}: {value:,.0f}")
    flash("تم حفظ الأهداف.", "ok")
    return redirect(url_for("page", key="goals"))


@app.route("/customers/export")
@page_required("customers")
def customers_export():
    user = current_user()
    store = selected_store(user)
    segment = request.args.get("segment", "")
    custs = an.customers(store)
    if segment in an.SEGMENTS:
        custs = [c for c in custs if c["segment"] == segment]
    custs.sort(key=lambda c: c["spent"], reverse=True)
    import csv, io
    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf)
    w.writerow(["العميل", "المتجر", "المدينة", "الشريحة", "عدد الطلبات", "إجمالي الإنفاق", "آخر طلب", "أيام من آخر طلب"])
    for c in custs:
        w.writerow([c["name"], STORES[c["store"]], c["city"], an.SEGMENTS[c["segment"]]["label"], c["orders"],
                    round(c["spent"], 2), c["last"], c["recency"]])
    db.log_action(user["id"], "customers_exported", f"تصدير عملاء: {segment or 'الكل'} — {STORES[store]}")
    return Response(buf.getvalue().encode("utf-8"), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=customers-{store}-{segment or 'all'}.csv"})


# ---------- users (owner/manager only) ----------

@app.route("/users")
@page_required("users")
def users():
    return render_template("users.html", users=db.list_users())


@app.route("/users/new", methods=["POST"])
@page_required("users")
def users_new():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "")
    store = request.form.get("store", "all")

    if not name or not email or len(password) < 8:
        flash("أدخل الاسم والبريد، وكلمة مرور لا تقل عن 8 أحرف.", "error")
    elif role not in ROLES or store not in STORES:
        flash("الدور أو المتجر غير صحيح.", "error")
    elif db.get_user_by_email(email):
        flash("هذا البريد مسجّل بالفعل.", "error")
    else:
        if role == "owner" and current_user()["role"] != "owner":
            abort(403)
        new_id = db.create_user(name, email, generate_password_hash(password, method="pbkdf2:sha256"), role, store)
        db.log_action(current_user()["id"], "user_created", f"إنشاء مستخدم #{new_id}: {email}")
        flash("تم إنشاء المستخدم.", "ok")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/toggle", methods=["POST"])
@page_required("users")
def users_toggle(user_id):
    target = db.get_user_by_id(user_id)
    if target is None:
        abort(404)
    if target["id"] == current_user()["id"]:
        flash("ما تقدرش توقف حسابك انت.", "error")
    elif target["role"] == "owner" and current_user()["role"] != "owner":
        abort(403)
    else:
        db.set_user_active(user_id, not target["active"])
        db.log_action(current_user()["id"], "user_toggled", f"تغيير حالة المستخدم #{user_id}")
        flash("تم تحديث حالة المستخدم.", "ok")
    return redirect(url_for("users"))


@app.route("/audit")
@page_required("users")
def audit():
    return render_template("audit.html", logs=db.list_audit(200))


@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="ليست لديك صلاحية للوصول لهذه الصفحة."), 403


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="الصفحة غير موجودة."), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400, message=e.description), 400


if __name__ == "__main__":
    with app.app_context():
        db.seed_owner_if_empty()  # محلياً: يوقف التشغيل لو بيانات المالك مش موجودة
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 8000)),
        debug=False,
    )
