"""يبني نسخة عرض ثابتة من اللوحة (بيانات تجريبية) لرفعها على GitHub Pages.

الاستخدام:
    .venv/bin/python tools/build_demo.py demo_site demo.growmatic.io

كل صفحة بتتحفظ في مسار ثابت: /{المتجر}/{الصفحة}/index.html
ومفيش أي كود سيرفر أو أسرار في الناتج.
"""

import html
import os
import re
import shutil
import sys
import tempfile
from urllib.parse import parse_qs, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# قاعدة بيانات مؤقتة وحساب عرض، بعيد عن بيانات الإنتاج
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "demo.db")
os.environ["OWNER_EMAIL"] = "demo@example.com"
os.environ["OWNER_PASSWORD"] = "demo-build-only-123"
os.environ.pop("APP_ENV", None)

import app as appmod  # noqa: E402
import db  # noqa: E402
import reports  # noqa: E402

STORES = ["all", "smooth", "glorias"]
PAGES = ["dashboard", "insights", "orders", "products", "inventory", "customers",
         "reports", "marketing", "goals", "simulator", "settings"]
MARKETING_DAYS = ["7", "30", "90"]


def main(out, domain):
    app = appmod.app
    app.config["TESTING"] = True
    app.config["STATIC_DEMO"] = True
    with app.app_context():
        conn = db.get_conn()
        conn.execute("UPDATE users SET name = 'عرض تجريبي'")
        conn.commit()

    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)

    client = app.test_client()
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    client.post("/login", data={"email": os.environ["OWNER_EMAIL"], "password": os.environ["OWNER_PASSWORD"], "csrf_token": token})

    default_period = {k: reports.periods(k)[0]["key"] for k in reports.KINDS}
    exports = set()

    def static_url(raw, store):
        """يحوّل رابط من اللوحة لمسار ثابت."""
        url = html.unescape(raw)
        if url.startswith(("/static/", "http", "#", "mailto:", "data:")):
            return raw
        parts = urlsplit(url)
        q = {k: v[0] for k, v in parse_qs(parts.query).items()}
        st = q.get("store", store)
        path = parts.path
        if path.startswith("/p/"):
            key = path[3:]
            if key == "reports":
                kind = q.get("kind", "month")
                kind = kind if kind in reports.KINDS else "month"
                return f"/{st}/reports/{kind}/{q.get('period', default_period[kind])}/"
            if key == "marketing":
                days = q.get("days", "30")
                return f"/{st}/marketing/{days if days in MARKETING_DAYS else '30'}/"
            return f"/{st}/{key}/"
        if path == "/reports/export":
            kind, fmt = q.get("kind", "month"), q.get("format", "xlsx")
            period = q.get("period", default_period[kind])
            exports.add(("report", st, kind, period, fmt))
            return f"/{st}/exports/report-{kind}-{period}.{fmt}"
        if path == "/customers/export":
            seg = q.get("segment", "")
            exports.add(("customers", st, seg))
            return f"/{st}/exports/customers-{seg or 'all'}.csv"
        if path in ("/", "/login"):
            return f"/{st}/dashboard/"
        return "#"

    def save(store, rel, url):
        r = client.get(url)
        if r.status_code != 200:
            raise SystemExit(f"فشل {url}: {r.status_code}")
        body = r.get_data(as_text=True)
        body = re.sub(r'(href|src|action)="([^"]*)"',
                      lambda m: f'{m.group(1)}="{static_url(m.group(2), store)}"', body)
        dest = os.path.join(out, store, rel, "index.html")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(body)

    count = 0
    for store in STORES:
        client.get(f"/p/dashboard?store={store}")  # يثبّت المتجر في الجلسة
        for key in PAGES:
            if key == "reports":
                for kind in reports.KINDS:
                    for p in reports.periods(kind):
                        save(store, f"reports/{kind}/{p['key']}", f"/p/reports?kind={kind}&period={p['key']}")
                        count += 1
            elif key == "marketing":
                for d in MARKETING_DAYS:
                    save(store, f"marketing/{d}", f"/p/marketing?days={d}")
                    count += 1
            else:
                save(store, key, f"/p/{key}")
                count += 1

    for item in sorted(exports):
        store = item[1]
        client.get(f"/p/dashboard?store={store}")
        if item[0] == "report":
            _, _, kind, period, fmt = item
            r = client.get(f"/reports/export?kind={kind}&period={period}&format={fmt}")
            name = f"report-{kind}-{period}.{fmt}"
        else:
            seg = item[2]
            r = client.get(f"/customers/export?segment={seg}")
            name = f"customers-{seg or 'all'}.csv"
        dest = os.path.join(out, store, "exports", name)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(r.data)

    shutil.copytree(os.path.join(ROOT, "static"), os.path.join(out, "static"))
    redirect = ('<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">'
                '<meta http-equiv="refresh" content="0; url=/all/dashboard/">'
                '<title>Growmatic</title><a href="/all/dashboard/">فتح اللوحة</a>')
    for name in ("index.html", "404.html"):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(redirect)
    with open(os.path.join(out, "robots.txt"), "w") as f:
        f.write("User-agent: *\nDisallow: /\n")
    with open(os.path.join(out, ".nojekyll"), "w") as f:
        f.write("")
    if domain:
        with open(os.path.join(out, "CNAME"), "w") as f:
            f.write(domain + "\n")
    print(f"تم: {count} صفحة و{len(exports)} ملف تصدير في {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo_site", sys.argv[2] if len(sys.argv) > 2 else "")
