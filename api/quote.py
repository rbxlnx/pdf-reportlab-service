import json
from io import BytesIO
from http.server import BaseHTTPRequestHandler

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm


PAGE_W, PAGE_H = A4
MARGIN = 12 * mm
HEADER_H = 22 * mm
FOOTER_H = 15 * mm
GAP = 4 * mm

TABLE_HEADER_H = 7 * mm
ROW_H = 8 * mm

COLS = [
    ("cod", 25 * mm),
    ("descr", 95 * mm),
    ("qty", 15 * mm),
    ("price", 25 * mm),
    ("total", 25 * mm),
]

LABELS = {"cod": "Cod.", "descr": "Descrizione", "qty": "Q.tà", "price": "Prezzo", "total": "Totale"}


def draw_header(c, data, page_no):
    x0 = MARGIN
    y_top = PAGE_H - MARGIN
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x0, y_top - 10 * mm, data.get("doc_title", "PREVENTIVO"))
    c.setFont("Helvetica", 9)
    c.drawRightString(PAGE_W - MARGIN, y_top - 10 * mm, f"Pagina {page_no}")
    c.drawString(x0, y_top - 18 * mm, f"Cliente: {data.get('cliente', '-')}")
    c.drawRightString(PAGE_W - MARGIN, y_top - 18 * mm, f"Data: {data.get('data', '-')}")


def draw_footer(c, data):
    y0 = MARGIN
    c.setFont("Helvetica", 8)
    c.drawString(MARGIN, y0 + 6 * mm, data.get("footer_left", "MITO Srl"))
    c.drawRightString(PAGE_W - MARGIN, y0 + 6 * mm, data.get("footer_right", "www.mito.it"))


def draw_table_header(c, x0, y):
    c.setFont("Helvetica-Bold", 9)
    x = x0
    for key, w in COLS:
        c.drawString(x + 2, y - 5 * mm, LABELS.get(key, key))
        x += w


def draw_row(c, x0, y, row):
    c.setFont("Helvetica", 9)
    x = x0

    values = {
        "cod": str(row.get("cod", "")),
        "descr": str(row.get("descr", ""))[:70],  # stabilità layout
        "qty": str(row.get("qty", "")),
        "price": str(row.get("price", "")),
        "total": str(row.get("total", "")),
    }

    for key, w in COLS:
        txt = values.get(key, "")
        if key in ("qty", "price", "total"):
            c.drawRightString(x + w - 2, y - 5 * mm, txt)
        else:
            c.drawString(x + 2, y - 5 * mm, txt)
        x += w


def build_pdf(payload: dict) -> bytes:
    rows = payload.get("rows", [])
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    page_no = 1
    while True:
        draw_header(c, payload, page_no)
        draw_footer(c, payload)

        body_top = PAGE_H - MARGIN - HEADER_H - GAP
        body_bottom = MARGIN + FOOTER_H + GAP

        x0 = MARGIN
        y = body_top

        draw_table_header(c, x0, y)
        y -= TABLE_HEADER_H

        lines_fit = int((y - body_bottom) // ROW_H)
        if lines_fit < 1:
            lines_fit = 1

        page_rows = rows[:lines_fit]
        rows = rows[lines_fit:]

        for r in page_rows:
            draw_row(c, x0, y, r)
            y -= ROW_H

        if not rows:
            break

        c.showPage()
        page_no += 1

    c.save()
    return buf.getvalue()


# 👇 IMPORTANTISSIMO: Vercel riconosce la function se esiste una variabile chiamata `handler`
#     che eredita BaseHTTPRequestHandler.
class handler(BaseHTTPRequestHandler):
    def _send_pdf(self, pdf_bytes: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", 'inline; filename="preventivo.pdf"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(pdf_bytes)

    def do_GET(self):
        # Test “cliccabile” da browser
        payload = {
            "doc_title": "TEST REPORTLAB",
            "cliente": "Rossi Srl",
            "data": "19/12/2025",
            "footer_left": "MITO Srl",
            "footer_right": "www.mito.it",
            "rows": [
                {"cod": "A001", "descr": "Prodotto 1", "qty": 1, "price": "€ 100,00", "total": "€ 100,00"},
                {"cod": "A002", "descr": "Prodotto 2 descrizione lunga", "qty": 2, "price": "€ 50,00", "total": "€ 100,00"},
            ],
        }
        self._send_pdf(build_pdf(payload))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = {}

        self._send_pdf(build_pdf(payload))
