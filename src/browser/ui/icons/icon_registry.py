"""Small, original outline SVGs for LightMq's browser controls.

The paths are authored for LightMq and use a shared 24 px view box and stroke
style. They are intentionally simple so they remain legible at toolbar sizes.
"""

ICON_MARKUP: dict[str, str] = {
    "arrow-left": '<path d="M19 12H5M12 19l-7-7 7-7"/>',
    "arrow-right": '<path d="M5 12h14m-7-7 7 7-7 7"/>',
    "reload": '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.6 9A7 7 0 0 1 18 6l2 6M4 12l2 6a7 7 0 0 0 12.4-3"/>',
    "stop": '<path d="m18 6-12 12M6 6l12 12"/>',
    "home": '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>',
    "bookmark": '<path d="M6 4.75A1.75 1.75 0 0 1 7.75 3h8.5A1.75 1.75 0 0 1 18 4.75V21l-6-3.75L6 21z"/>',
    "bookmark-filled": '<path d="M6 4.75A1.75 1.75 0 0 1 7.75 3h8.5A1.75 1.75 0 0 1 18 4.75V21l-6-3.75L6 21z" fill="__COLOR__"/>',
    "bookmarks": '<path d="M5 5.5A1.5 1.5 0 0 1 6.5 4H17v14H6.5A1.5 1.5 0 0 0 5 19.5z"/><path d="M19 6h1v14H7"/>',
    "download": '<path d="M12 3v12m-5-5 5 5 5-5"/><path d="M5 17v3h14v-3"/>',
    "history": '<path d="M3 12a9 9 0 1 0 2.64-6.36L3 8"/><path d="M3 3v5h5m4-1v5l3 2"/>',
    "settings": '<path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z"/><path d="m19.4 15 .1.1a1.8 1.8 0 1 1-2.55 2.55l-.1-.1a1.8 1.8 0 0 0-3.06 1.27v.28a1.8 1.8 0 1 1-3.6 0v-.15a1.8 1.8 0 0 0-3.06-1.27l-.1.1a1.8 1.8 0 1 1-2.55-2.55l.1-.1a1.8 1.8 0 0 0-1.27-3.06h-.28a1.8 1.8 0 1 1 0-3.6h.15a1.8 1.8 0 0 0 1.27-3.06l-.1-.1A1.8 1.8 0 1 1 6.9 2.63l.1.1a1.8 1.8 0 0 0 3.06-1.27v-.28a1.8 1.8 0 1 1 3.6 0v.15a1.8 1.8 0 0 0 3.06 1.27l.1-.1a1.8 1.8 0 1 1 2.55 2.55l-.1.1a1.8 1.8 0 0 0 1.27 3.06h.28a1.8 1.8 0 1 1 0 3.6h-.15A1.8 1.8 0 0 0 19.4 15z" transform="translate(1.3 1.3) scale(.89)"/>',
    "menu": '<circle cx="12" cy="5" r="1.2" fill="__COLOR__"/><circle cx="12" cy="12" r="1.2" fill="__COLOR__"/><circle cx="12" cy="19" r="1.2" fill="__COLOR__"/>',
    "profile": '<circle cx="12" cy="8" r="3.5"/><path d="M4.5 21a7.5 7.5 0 0 1 15 0z"/>',
    "search": '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/>',
    "tab-search": '<rect x="3" y="4" width="14" height="13" rx="2"/><path d="M7 8h6m-6 3h4"/><circle cx="17" cy="16" r="3.2"/><path d="m19.4 18.4 2 2"/>',
    "lock": '<rect x="4.5" y="10" width="15" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 4v3"/>',
    "shield": '<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11z"/><path d="m9 12 2 2 4-4"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "close": '<path d="m18 6-12 12M6 6l12 12"/>',
    "pin": '<path d="m16 3 5 5-4 1-4 4 1 4-2 2-4-6-5-5 2-2 4 1 4-4zM10 14l-6 7"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "chevron-right": '<path d="m9 6 6 6-6 6"/>',
    "new-window": '<rect x="3" y="5" width="14" height="14" rx="2"/><path d="M9 3h10a2 2 0 0 1 2 2v10m-8-4 7-7m-6 0h6v6"/>',
    "incognito": '<path d="M3 6h18l-2-3H5zM2 12h8m4 0h8"/><circle cx="7" cy="15" r="3"/><circle cx="17" cy="15" r="3"/><path d="M10 15h4m-8 6 1-3m10 3-1-3"/>',
    "groups": '<rect x="3" y="4" width="13" height="14" rx="2"/><path d="M7 8h5M7 11h5M7 14h3"/><path d="M18 8h3v12H8v-2"/>',
    "zoom-in": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5m-11-13v5m-2.5-2.5h5"/>',
    "zoom-out": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5m-14-10h7"/>',
    "zoom-reset": '<path d="M4 8a8 8 0 1 1-1 6"/><path d="M4 3v5h5m3-1v5l3 2"/>',
    "print": '<path d="M7 8V3h10v5M7 17H5a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M7 14h10v7H7zM17 11h.01"/>',
    "devtools": '<path d="m8 5-6 7 6 7m8-14 6 7-6 7m-3-16-2 18"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.5 2.5 0 1 1 4.1 1.9c-1.1.9-1.7 1.3-1.7 2.6m0 3h.01"/>',
    "exit": '<path d="M10 17l5-5-5-5m5 5H3"/><path d="M12 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7"/>',
    "palette": '<path d="M12 3a9 9 0 1 0 0 18h1.2a2 2 0 0 0 1.5-3.3 1.8 1.8 0 0 1 1.4-3h1.3a3.6 3.6 0 0 0 3.6-3.6A8.1 8.1 0 0 0 12 3z"/><circle cx="7.5" cy="11" r=".8" fill="__COLOR__"/><circle cx="10" cy="7.5" r=".8" fill="__COLOR__"/><circle cx="15" cy="7.5" r=".8" fill="__COLOR__"/>',
    "keyboard": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M9 9h.01M12 9h.01M15 9h.01M18 9h.01M6 12h.01M9 12h.01M12 12h.01M15 12h.01M18 12h.01M7 15h10"/>',
    "sliders": '<path d="M4 21v-7m0-4V3m8 18v-9m0-4V3m8 18v-5m0-4V3M2 14h4m4-6h4m4 6h4"/>',
    "tabs": '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M7 6V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v2"/>',
    "folder": '<path d="M3 6a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "edit": '<path d="m15 5 4 4M4 20l4-.8L19 8a2.8 2.8 0 0 0-4-4L4 15z"/>',
    "arrow-up": '<path d="M12 19V5m-7 7 7-7 7 7"/>',
    "arrow-down": '<path d="M12 5v14m7-7-7 7-7-7"/>',
}


def svg_document(name: str, color: str) -> bytes:
    """Build a self-contained SVG document from a trusted LightMq path."""
    try:
        markup = ICON_MARKUP[name]
    except KeyError as error:
        raise ValueError(f"Unknown LightMq icon: {name}") from error
    markup = markup.replace("__COLOR__", color)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24"><g fill="none" '
        f'stroke="{color}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round">{markup}</g></svg>'
    ).encode("utf-8")
