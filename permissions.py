"""تعريف الصفحات والأدوار والمتاجر. أي صلاحية جديدة تُضاف هنا."""

PAGES = {
    "dashboard": {"label": "الرئيسية", "icon": "home", "group": "عام"},
    "orders": {"label": "الطلبات", "icon": "bag", "group": "العمليات"},
    "products": {"label": "المنتجات", "icon": "tag", "group": "العمليات"},
    "inventory": {"label": "المخزون", "icon": "boxes", "group": "العمليات"},
    "customers": {"label": "العملاء", "icon": "users", "group": "العمليات"},
    "reports": {"label": "التقارير", "icon": "chart", "group": "التحليل"},
    "settings": {"label": "الإعدادات", "icon": "gear", "group": "الإدارة"},
    "users": {"label": "المستخدمون", "icon": "shield", "group": "الإدارة"},
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
