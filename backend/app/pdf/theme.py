from functools import lru_cache
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ASSETS = Path(__file__).resolve().parents[1] / "assets"
LOGO = ASSETS / "anicraze-logo.png"
INK = colors.HexColor("#171719")
MUTED = colors.HexColor("#55565B")
LINE = colors.HexColor("#D9DADD")
PALE = colors.HexColor("#F4F4F5")
RED = colors.HexColor("#B21D25")
REGULAR = "AnicrazeSans"
BOLD = "AnicrazeSans-Bold"


@lru_cache(maxsize=1)
def styles():
    for name, filename in [(REGULAR, "NotoSans-Regular.ttf"), (BOLD, "NotoSans-Bold.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(ASSETS / "fonts" / filename)))
    pdfmetrics.registerFontFamily(REGULAR, normal=REGULAR, bold=BOLD, italic=REGULAR, boldItalic=BOLD)
    base = dict(fontName=REGULAR, fontSize=9, leading=13, textColor=INK, splitLongWords=True)
    result = {"body": ParagraphStyle("body", **base)}
    for key, overrides in {
        "title": dict(fontName=BOLD, fontSize=21, leading=25, alignment=2),
        "small": dict(fontSize=8, leading=11, textColor=MUTED),
        "section": dict(fontName=BOLD, fontSize=12, leading=16, spaceBefore=12, spaceAfter=7, keepWithNext=True),
        "label": dict(fontName=BOLD, fontSize=8, leading=11, textColor=MUTED),
        "value": dict(fontName=BOLD, fontSize=17, leading=22),
        "head": dict(fontName=BOLD, fontSize=8, leading=11, textColor=colors.white),
        "cell": dict(fontSize=8.5, leading=12),
        "total": dict(fontName=BOLD, fontSize=9, leading=13),
    }.items():
        result[key] = ParagraphStyle(key, **{**base, **overrides})
    return result
