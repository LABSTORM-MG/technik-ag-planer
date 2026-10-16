from . import navigation as sections
from .design import THEME_COLOR


def navigation(request):
    return {
        "theme_color": THEME_COLOR,
        "nav_sidebar": sections.SIDEBAR,
        "nav_mobile_left": sections.MOBILE_LEFT,
        "nav_mobile_right": sections.MOBILE_RIGHT,
        "nav_mobile_more": sections.MOBILE_MORE,
        "nav_new_items": sections.NEW_ITEMS,
        "nav_settings": sections.SETTINGS,
        # Zähler ungelesener Board-Nachrichten – echte Werte ab Meilenstein 5
        "nav_unread_count": 0,
    }
