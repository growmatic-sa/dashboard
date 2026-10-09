"""تعريف الصفحات والأدوار والمتاجر. أي صلاحية جديدة تُضاف هنا."""

PAGES = {
    "dashboard": {"label": "الرئيسية"},
    "orders": {"label": "الطلبات"},
    "products": {"label": "المنتجات"},
    "inventory": {"label": "المخزون"},
    "customers": {"label": "العملاء"},
    "reports": {"label": "التقارير"},
    "settings": {"label": "الإعدادات"},
    "users": {"label": "المستخدمون"},
}

ROLES = {
    "owner": "مالك",
    "manager": "مدير",
    "inventory": "مسؤول مخزون",
    "orders": "موظف طلبات",
    "viewer": "مشاهد",
}

# الصفحات المسموحة لكل دور
ROLE_PAGES = {
    "owner": set(PAGES),
    "manager": set(PAGES) - {"users", "settings"},
    "inventory": {"dashboard", "products", "inventory"},
    "orders": {"dashboard", "orders", "customers"},
    "viewer": {"dashboard", "reports"},
}

# all = كل المتاجر، والباقي مفاتيح المتاجر
STORES = {
    "all": "كل المتاجر",
    "smooth": "سموذ",
    "glorias": "قلوريز",
}


def can_access_page(role, page):
    return page in ROLE_PAGES.get(role, set())
