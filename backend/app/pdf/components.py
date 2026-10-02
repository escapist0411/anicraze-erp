import io
from datetime import datetime, timezone
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import CondPageBreak, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config.business import BUSINESS_PHONE_DISPLAY
from app.pdf.formatters import format_datetime
from app.pdf.theme import BOLD, INK, LINE, LOGO, MUTED, PALE, RED, REGULAR, styles


def p(value, kind="body", align=None):
    style = styles()[kind]
    if align is not None:
        style = style.clone(f"{kind}-{align}", alignment=align)
    return Paragraph(escape(str(value if value is not None else "-")).replace("\n", "<br/>"), style)


class NumberedCanvas(Canvas):
    """Replay pages once their final count is known, preserving embedded assets."""
    def __init__(self, *args, label, generated, preview=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.states = []
        self.footer_label = label
        self.generated_label = generated
        self.preview = preview

    def showPage(self):
        self.states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        count = len(self.states)
        for state in self.states:
            self.__dict__.update(state)
            width, height = self._pagesize
            self.setStrokeColor(LINE); self.line(36, 44, width - 36, 44)
            self.setFont(REGULAR, 7.5); self.setFillColor(MUTED)
            self.drawString(36, 30, f"ANICRAZE  |  {self.footer_label}")
            self.drawRightString(width - 36, 30, f"Page {self._pageNumber} of {count}")
            self.drawString(36, 18, f"Generated {self.generated_label}")
            if self.preview:
                self.setFont(BOLD, 7.5); self.drawRightString(width - 36, 18, "SAMPLE PREVIEW")
            if self._pageNumber > 1:
                self.setFont(BOLD, 8); self.drawString(36, height - 24, "ANICRAZE")
                self.setFont(REGULAR, 8); self.drawRightString(width - 36, height - 24, "Continued")
            super().showPage()
        super().save()


class Document:
    def __init__(self, title, *, wide=False, preview=False, internal=True, generated=None):
        styles()
        self.title, self.preview, self.internal = title, preview, internal
        self.generated = generated or datetime.now(timezone.utc)
        self.page = landscape(A4) if wide else A4
        self.width = self.page[0] - 72
        self.story = []

    def header(self, subtitle=None, metadata=()):
        iw, ih = ImageReader(str(LOGO)).getSize()
        logo = Image(str(LOGO), width=120, height=120 * ih / iw)
        heading = [p(self.title, "title")]
        if subtitle:
            heading += [Spacer(1, 5), p(subtitle, "small", 2)]
        badge = "SAMPLE PREVIEW" if self.preview else "CONFIDENTIAL" if self.internal else None
        if badge:
            heading += [Spacer(1, 5), p(badge, "label", 2)]
        header = Table([[logo, heading]], colWidths=[145, self.width - 145])
        header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 15), ("LINEBELOW", (0, 0), (-1, -1), 1.2, INK)]))
        self.story += [header, Spacer(1, 14)]
        if metadata:
            self.metadata(metadata)

    def metadata(self, items):
        cells = [[p(label.upper(), "label"), p(value)] for label, value in items if value is not None]
        if not cells:
            return
        table = Table(cells, colWidths=[95, self.width - 95])
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        self.story += [table, Spacer(1, 5)]

    def section(self, title):
        self.story.append(p(title, "section"))

    def note(self, text):
        self.story += [Spacer(1, 7), p(text, "small")]

    def kpis(self, entries, columns=3):
        if not entries:
            return
        count = min(columns, len(entries))
        cell_width = (self.width - (count - 1) * 8) / count
        for offset in range(0, len(entries), count):
            row = []
            for label, value in entries[offset:offset + count]:
                card = Table([[p(label.upper(), "label")], [p(value, "value")]], colWidths=[cell_width])
                card.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), .5, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, 0), 10), ("BOTTOMPADDING", (0, -1), (-1, -1), 12)]))
                if row: row.append("")
                row.append(card)
            while len(row) < count * 2 - 1:
                row.append("")
            widths = [cell_width if i % 2 == 0 else 8 for i in range(count * 2 - 1)]
            grid = Table([row], colWidths=widths)
            grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
            self.story += [grid, Spacer(1, 6)]

    def table(self, headers, rows, *, weights=None, numeric=(), total=None, padding=6):
        if not rows:
            self.note("No records found for the selected period.")
            return
        weights = weights or [1] * len(headers)
        widths = [self.width * w / sum(weights) for w in weights]
        data = [[p(h, "head", 2 if i in numeric else 0) for i, h in enumerate(headers)]]
        for row in rows:
            data.append([p(v, "cell", 2 if i in numeric else 0) for i, v in enumerate(row)])
        if total is not None:
            data.append([p(v, "total", 2 if i in numeric else 0) for i, v in enumerate(total)])
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
        commands = [("BACKGROUND", (0, 0), (-1, 0), INK), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), padding), ("BOTTOMPADDING", (0, 0), (-1, -1), padding), ("LINEBELOW", (0, 0), (-1, 0), .8, INK), ("LINEBELOW", (0, -1), (-1, -1), .5, LINE)]
        if total is not None:
            commands += [("LINEABOVE", (0, -1), (-1, -1), 1, INK), ("BACKGROUND", (0, -1), (-1, -1), PALE)]
        table.setStyle(TableStyle(commands))
        if self.story and isinstance(self.story[-1], Paragraph) and self.story[-1].style.name == "section":
            # Keep a heading with at least the table header and its first row,
            # while allowing long tables to begin in the remaining page space.
            heading = self.story.pop()
            heading.keepWithNext = False
            first_rows = Table(data[:2], colWidths=widths)
            first_rows.setStyle(TableStyle(commands))
            minimum = heading.wrap(self.width, self.page[1])[1] + heading.getSpaceBefore() + heading.getSpaceAfter() + first_rows.wrap(self.width, self.page[1])[1]
            self.story.extend([CondPageBreak(minimum), heading])
        self.story.append(table)

    def status(self, value):
        badge = Table([[p(str(value).replace("_", " "), "label")]], hAlign="LEFT")
        badge.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), .7, INK), ("BACKGROUND", (0, 0), (-1, -1), PALE), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        self.story += [badge, Spacer(1, 10)]

    def build(self):
        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=self.page, leftMargin=36, rightMargin=36, topMargin=42, bottomMargin=60, title=f"ANICRAZE | {self.title}", author="ANICRAZE", pageCompression=1)
        footer = (f"Internal Business Report | {BUSINESS_PHONE_DISPLAY}" if self.internal else f"Thank you for shopping with us | {BUSINESS_PHONE_DISPLAY}")
        doc.build(self.story, canvasmaker=lambda *a, **kw: NumberedCanvas(*a, label=footer, generated=format_datetime(self.generated), preview=self.preview, **kw))
        return output.getvalue()
