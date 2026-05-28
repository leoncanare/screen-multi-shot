"""
icons.py
Heroicons outline — renderizados a CTkImage via cairosvg.
Uso: ic.get("rocket-launch", 18)  →  CTkImage  (o None si cairosvg no está)
"""
import io
from typing import Optional

# ── SVG strings (Heroicons v2 outline) ───────────────────────────
_SVGS: dict[str, str] = {
    "globe-alt": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 21C16.1926 21 19.7156 18.1332 20.7157 14.2529M12 21C7.80742 21 4.28442 18.1332 '
        '3.2843 14.2529M12 21C14.4853 21 16.5 16.9706 16.5 12C16.5 7.02944 14.4853 3 12 3M12 21C9.51472 '
        '21 7.5 16.9706 7.5 12C7.5 7.02944 9.51472 3 12 3M12 3C15.3652 3 18.299 4.84694 19.8431 7.58245M'
        '12 3C8.63481 3 5.70099 4.84694 4.15692 7.58245M19.8431 7.58245C17.7397 9.40039 14.9983 10.5 12 '
        '10.5C9.00172 10.5 6.26027 9.40039 4.15692 7.58245M19.8431 7.58245C20.5797 8.88743 21 10.3946 21 '
        '12C21 12.778 20.9013 13.5329 20.7157 14.2529M20.7157 14.2529C18.1334 15.6847 15.1619 16.5 12 '
        '16.5C8.8381 16.5 5.86662 15.6847 3.2843 14.2529M3.2843 14.2529C3.09871 13.5329 3 12.778 3 12C3 '
        '10.3946 3.42032 8.88743 4.15692 7.58245" stroke="#0F172A" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "folder-open": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M3.74999 9.77602C3.86203 9.7589 3.97698 9.75 4.09426 9.75H19.9057C20.023 9.75 20.138 '
        '9.7589 20.25 9.77602M3.74999 9.77602C2.55399 9.9588 1.68982 11.0788 1.86688 12.3182L2.72402 '
        '18.3182C2.88237 19.4267 3.83169 20.25 4.95141 20.25H19.0486C20.1683 20.25 21.1176 19.4267 '
        '21.276 18.3182L22.1331 12.3182C22.3102 11.0788 21.446 9.9588 20.25 9.77602M3.74999 9.77602V6'
        'C3.74999 4.75736 4.75735 3.75 5.99999 3.75H9.87867C10.2765 3.75 10.658 3.90804 10.9393 '
        '4.18934L13.0607 6.31066C13.342 6.59197 13.7235 6.75 14.1213 6.75H18C19.2426 6.75 20.25 '
        '7.75736 20.25 9V9.77602" stroke="#0F172A" stroke-width="1.5" stroke-linecap="round" '
        'stroke-linejoin="round"/></svg>'
    ),
    "folder": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M2.25 12.75V12C2.25 10.7574 3.25736 9.75 4.5 9.75H19.5C20.7426 9.75 21.75 10.7574 '
        '21.75 12V12.75M13.0607 6.31066L10.9393 4.18934C10.658 3.90804 10.2765 3.75 9.87868 3.75H4.5'
        'C3.25736 3.75 2.25 4.75736 2.25 6V18C2.25 19.2426 3.25736 20.25 4.5 20.25H19.5C20.7426 20.25 '
        '21.75 19.2426 21.75 18V9C21.75 7.75736 20.7426 6.75 19.5 6.75H14.1213C13.7235 6.75 13.342 '
        '6.59197 13.0607 6.31066Z" stroke="#0F172A" stroke-width="1.5" stroke-linecap="round" '
        'stroke-linejoin="round"/></svg>'
    ),
    "arrow-path": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M16.0228 9.34841H21.0154V9.34663M2.98413 19.6444V14.6517M2.98413 14.6517L7.97677 '
        '14.6517M2.98413 14.6517L6.16502 17.8347C7.15555 18.8271 8.41261 19.58 9.86436 19.969C14.2654 '
        '21.1483 18.7892 18.5364 19.9685 14.1353M4.03073 9.86484C5.21 5.46374 9.73377 2.85194 14.1349 '
        '4.03121C15.5866 4.4202 16.8437 5.17312 17.8342 6.1655L21.0154 9.34663M21.0154 4.3558V9.34663" '
        'stroke="#0F172A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "rocket-launch": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M15.5904 14.3696C15.6948 14.8128 15.75 15.275 15.75 15.75C15.75 19.0637 13.0637 21.75 '
        '9.75 21.75V16.9503M15.5904 14.3696C19.3244 11.6411 21.75 7.22874 21.75 2.25C16.7715 2.25021 '
        '12.3595 4.67586 9.63122 8.40975M15.5904 14.3696C13.8819 15.6181 11.8994 16.514 9.75 16.9503M'
        '9.63122 8.40975C9.18777 8.30528 8.72534 8.25 8.25 8.25C4.93629 8.25 2.25 10.9363 2.25 14.25H'
        '7.05072M9.63122 8.40975C8.38285 10.1183 7.48701 12.1007 7.05072 14.25M9.75 16.9503C9.64659 '
        '16.9713 9.54279 16.9912 9.43862 17.0101C8.53171 16.291 7.70991 15.4692 6.99079 14.5623C7.00969 '
        '14.4578 7.02967 14.3537 7.05072 14.25M4.81191 16.6408C3.71213 17.4612 3 18.7724 3 20.25C3 '
        '20.4869 3.0183 20.7194 3.05356 20.9464C3.28054 20.9817 3.51313 21 3.75 21C5.22758 21 6.53883 '
        '20.2879 7.35925 19.1881M16.5 9C16.5 9.82843 15.8284 10.5 15 10.5C14.1716 10.5 13.5 9.82843 '
        '13.5 9C13.5 8.17157 14.1716 7.5 15 7.5C15.8284 7.5 16.5 8.17157 16.5 9Z" stroke="#0F172A" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "x-circle": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M9.75 9.75L14.25 14.25M14.25 9.75L9.75 14.25M21 12C21 16.9706 16.9706 21 12 21C7.02944 '
        '21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="#0F172A" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "sparkles": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M9.8132 15.9038L9 18.75L8.1868 15.9038C7.75968 14.4089 6.59112 13.2403 5.09619 '
        '12.8132L2.25 12L5.09619 11.1868C6.59113 10.7597 7.75968 9.59112 8.1868 8.09619L9 5.25L9.8132 '
        '8.09619C10.2403 9.59113 11.4089 10.7597 12.9038 11.1868L15.75 12L12.9038 12.8132C11.4089 '
        '13.2403 10.2403 14.4089 9.8132 15.9038Z" stroke="#0F172A" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M18.2589 8.71454L18 9.75L17.7411 8.71454C17.4388 7.50533 16.4947 6.56117 15.2855 '
        '6.25887L14.25 6L15.2855 5.74113C16.4947 5.43883 17.4388 4.49467 17.7411 3.28546L18 2.25L'
        '18.2589 3.28546C18.5612 4.49467 19.5053 5.43883 20.7145 5.74113L21.75 6L20.7145 6.25887C'
        '19.5053 6.56117 18.5612 7.50533 18.2589 8.71454Z" stroke="#0F172A" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M16.8942 20.5673L16.5 21.75L16.1058 20.5673C15.8818 19.8954 15.3546 19.3682 14.6827 '
        '19.1442L13.5 18.75L14.6827 18.3558C15.3546 18.1318 15.8818 17.6046 16.1058 16.9327L16.5 15.75'
        'L16.8942 16.9327C17.1182 17.6046 17.6454 18.1318 18.3173 18.3558L19.5 18.75L18.3173 19.1442C'
        '17.6454 19.3682 17.1182 19.8954 16.8942 20.5673Z" stroke="#0F172A" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "plus": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 4.5V19.5M19.5 12L4.5 12" stroke="#0F172A" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "x-mark": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M6 18L18 6M6 6L18 18" stroke="#0F172A" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "computer-desktop": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M9 17.25V18.2574C9 19.053 8.68393 19.8161 8.12132 20.3787L7.5 21H16.5L15.8787 '
        '20.3787C15.3161 19.8161 15 19.053 15 18.2574V17.25M21 5.25V15C21 16.2426 19.9926 17.25 18.75 '
        '17.25H5.25C4.00736 17.25 3 16.2426 3 15V5.25M21 5.25C21 4.00736 19.9926 3 18.75 3H5.25C4.00736 '
        '3 3 4.00736 3 5.25M21 5.25V12C21 13.2426 19.9926 14.25 18.75 14.25H5.25C4.00736 14.25 3 '
        '13.2426 3 12V5.25" stroke="#0F172A" stroke-width="1.5" stroke-linecap="round" '
        'stroke-linejoin="round"/></svg>'
    ),
    "device-phone-mobile": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M10.5 1.5H8.25C7.00736 1.5 6 2.50736 6 3.75V20.25C6 21.4926 7.00736 22.5 8.25 '
        '22.5H15.75C16.9926 22.5 18 21.4926 18 20.25V3.75C18 2.50736 16.9926 1.5 15.75 1.5H13.5M10.5 '
        '1.5V3H13.5V1.5M10.5 1.5H13.5M10.5 20.25H13.5" stroke="#0F172A" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "device-tablet": (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M10.5 19.5H13.5M6.75 21.75H17.25C18.4926 21.75 19.5 20.7426 19.5 19.5V4.5C19.5 '
        '3.25736 18.4926 2.25 17.25 2.25H6.75C5.50736 2.25 4.5 3.25736 4.5 4.5V19.5C4.5 20.7426 '
        '5.50736 21.75 6.75 21.75Z" stroke="#0F172A" stroke-width="1.5" stroke-linecap="round" '
        'stroke-linejoin="round"/></svg>'
    ),
}

# ── Caché ─────────────────────────────────────────────────────────
_cache: dict = {}


def _render(name: str, size: int, stroke: str):
    svg = _SVGS.get(name)
    if not svg:
        return None
    svg = svg.replace('stroke="#0F172A"', f'stroke="{stroke}"')
    try:
        import cairosvg
        from PIL import Image
        png = cairosvg.svg2png(bytestring=svg.encode(), output_width=size, output_height=size)
        return Image.open(io.BytesIO(png))
    except Exception:
        return None


def get(name: str, size: int = 18):
    """
    Devuelve un CTkImage del heroicon solicitado, con variante dark/light.
    Retorna None si cairosvg no está disponible.
    """
    import customtkinter as ctk

    key = (name, size)
    if key in _cache:
        return _cache[key]

    light_img = _render(name, size, "#1E293B")   # icono oscuro → tema claro
    dark_img  = _render(name, size, "#CBD5E1")   # icono claro  → tema oscuro

    if light_img and dark_img:
        result = ctk.CTkImage(light_image=light_img, dark_image=dark_img, size=(size, size))
    else:
        result = None

    _cache[key] = result
    return result
