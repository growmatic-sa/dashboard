import os
import secrets
from functools import wraps

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import envfile
envfile.load()

import db  # noqa: E402  (يجب أن يأتي بعد تحميل .env)
from permissions import PAGES, ROLES, STORES, can_access_page

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"

db.init_app(app)


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


@app.context_processor
def inject_globals():
    user = current_user()
    return {
        "csrf_token": csrf_token,
        "current_user": user,
        "pages": PAGES,
        "role_names": ROLES,
        "store_names": STORES,
        "can_page": lambda page: bool(user) and can_access_page(user["role"], page),
    }


# ---------- auth ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.get_user_by_email(email)
        if user and user["active"] and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["csrf"] = secrets.token_hex(16)
            db.log_action(user["id"], "login", "تسجيل دخول")
            return redirect(url_for("index"))
        db.log_action(None, "login_failed", f"محاولة فاشلة: {email}")
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


@app.route("/p/<key>")
@login_required
def page(key):
    if key not in PAGES:
        abort(404)
    if not can_access_page(current_user()["role"], key):
        abort(403)
    return render_template("page.html", key=key, title=PAGES[key]["label"])


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
        db.seed_owner_if_empty()
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 8000)),
        debug=False,
    )
