from . import navigation as sections
from .design import THEME_COLOR


def navigation(request):
    membership = getattr(request, "membership", None)
    new_items = [
        item
        for item in sections.NEW_ITEMS
        if membership is not None and membership.has_perm(item["perm"])
    ]
    return {
        "theme_color": THEME_COLOR,
        "nav_sidebar": sections.SIDEBAR,
        "nav_mobile_left": sections.MOBILE_LEFT,
        "nav_mobile_right": sections.MOBILE_RIGHT,
        "nav_mobile_more": sections.MOBILE_MORE,
        "nav_new_items": new_items,
        "nav_settings": sections.SETTINGS,
        # Zähler ungelesener Board-Nachrichten – echte Werte ab Meilenstein 5
        "nav_unread_count": 0,
        "current_membership": membership,
        "current_organization": getattr(request, "organization", None),
        "user_memberships": getattr(request, "memberships", []),
        "org_perms": getattr(request, "org_perms", None),
    }
