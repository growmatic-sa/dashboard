"""هوية كل متجر: اللون الأساسي واللوجو. اللوجوهات محفوظة في static/brands/."""

DEFAULT_BRAND = {
    "name": "لوحة المتاجر",
    "color": "#313131",
    "logo": None,
}

BRANDS = {
    "smooth": {
        "name": "سموذ",
        "color": "#c03038",
        "logo": "brands/smooth-logo.webp",
    },
    "glorias": {
        "name": "قلوريز",
        "color": "#e86030",
        "logo": "brands/glorias-logo.webp",
    },
}


def brand_for(store):
    return BRANDS.get(store, DEFAULT_BRAND)
