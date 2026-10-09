"""هوية اللوحة وهوية كل متجر.

كل هوية فيها درجات للوضع الفاتح والداكن:
  primary  اللون الأساسي (الأزرار، التحديد، الرسم البياني)
  strong   درجة أغمق للتمرير والضغط
  soft     خلفية فاتحة جداً للوسوم والتظليل
  glow     اللون التاني في التدرّج
  fill     خلفية الأزرار اللي عليها نص أبيض (تباين كافي)
"""

PANEL = {
    "key": "all",
    "name": "Growmatic",
    "tagline": "لوحة إدارة المتاجر",
    "logo": None,
    "light": {"fill": "#5b4cf0", "primary": "#5b4cf0", "strong": "#4433d6", "soft": "#efedff", "glow": "#a497ff"},
    "dark": {"fill": "#6a5cf5", "primary": "#8c80ff", "strong": "#a499ff", "soft": "#231f4a", "glow": "#5b4cf0"},
}

BRANDS = {
    "smooth": {
        "key": "smooth",
        "name": "سموذ",
        "tagline": "Smooth Cosmetics",
        "logo": "brands/smooth-logo.webp",
        "light": {"fill": "#c03038", "primary": "#c03038", "strong": "#9c222a", "soft": "#fdecee", "glow": "#f890a8"},
        "dark": {"fill": "#c8364a", "primary": "#f0697a", "strong": "#f78b98", "soft": "#3a1a20", "glow": "#c03038"},
    },
    "glorias": {
        "key": "glorias",
        "name": "قلوريز",
        "tagline": "Glories Eyelashes",
        "logo": "brands/glorias-logo.webp",
        "light": {"fill": "#c24c1d", "primary": "#e05a28", "strong": "#b9461b", "soft": "#fdf0e9", "glow": "#ff8c82"},
        "dark": {"fill": "#c24c1d", "primary": "#f5864f", "strong": "#f9a072", "soft": "#3a2216", "glow": "#e05a28"},
    },
}

# ألوان المقارنة بين المتجرين في الرسوم: فرق واضح في الإضاءة عشان تتميّز حتى مع ضعف تمييز الألوان
SERIES = {
    "smooth": {"light": "#b52a36", "dark": "#f0697a"},
    "glorias": {"light": "#f0a066", "dark": "#c9662f"},
}


def brand_for(store):
    return BRANDS.get(store, PANEL)
