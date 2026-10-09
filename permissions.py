"""تعريف الصفحات والأدوار والمتاجر. أي صلاحية جديدة تُضاف هنا."""

PAGES = {
    "dashboard": {"label": "الرئيسية", "icon": "home", "group": "عام"},
    "insights": {"label": "الرؤى والتوصيات", "icon": "bulb", "group": "عام"},
    "orders": {"label": "الطلبات", "icon": "bag", "group": "العمليات"},
    "products": {"label": "المنتجات", "icon": "tag", "group": "العمليات"},
    "inventory": {"label": "المخزون", "icon": "boxes", "group": "العمليات"},
    "customers": {"label": "العملاء", "icon": "users", "group": "العمليات"},
    "reports": {"label": "التقارير", "icon": "chart", "group": "التحليل والقرار"},
    "marketing": {"label": "التسويق", "icon": "megaphone", "group": "التحليل والقرار"},
    "goals": {"label": "الأهداف والتوقعات", "icon": "target", "group": "التحليل والقرار"},
    "simulator": {"label": "محاكي القرارات", "icon": "sliders", "group": "التحليل والقرار"},
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
    "viewer": {"dashboard", "insights", "reports", "marketing", "goals"},
}

# صفحات بتسمح بالتعديل (مش بس العرض)
EDIT_PAGES = {
    "goals": {"owner", "manager"},
}

# all = كل المتاجر، والباقي مفاتيح المتاجر
STORES = {
    "all": "كل المتاجر",
    "smooth": "سموذ",
    "glorias": "قلوريز",
}


def can_access_page(role, page):
    return page in ROLE_PAGES.get(role, set())


def can_edit(role, page):
    return role in EDIT_PAGES.get(page, set())
