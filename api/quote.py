import json
from io import BytesIO
from http.server import BaseHTTPRequestHandler

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth


PAGE_W, PAGE_H = A4
MARGIN = 12 * mm

# Layout stile "Preventivo vecchio"
HEADER_H = 26 * mm
FOOTER_H = 14 * mm
GAP = 4 * mm

TABLE_HEADER_H = 8 * mm
ROW_MIN_H = 8 * mm
LEADING = 4.2 * mm  # interlinea descrizione multiline

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"
FS = 9

# Colonne (come schema tuo)
COLS = [
    ("cod", 25 * mm),
    ("descr", 95 * mm),
    ("qty", 15 * mm),
    ("price", 25 * mm),
    ("total", 25 * mm),
]
LABELS = {"cod": "Cod.", "descr": "Descrizione", "qty": "Q.tà", "price": "Prezzo", "total": "Totale"}


def wrap_text(text, font_name, font_size, max_width):
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if stringWidth(test, font_name, font_size) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_header(c, data, page_no, total_pages=None):
    x0 = MARGIN
    y_top = PAGE_H - MARGIN

    # Titolo a sinistra
    c.setFont(FONT_B, 14)
    c.drawString(x0, y_top - 8 * mm, data.get("doc_title", "PREVENTIVO"))

    # Pagina a destra (nel vecchio è "Pagina 1")
    c.setFont(FONT, 10)
    c.drawRightString(PAGE_W - MARGIN, y_top - 8 * mm, f"Pagina {page_no}")

    # Cliente a sinistra, Data a destra
    c.setFont(FONT, 10)
    c.drawString(x0, y_top - 18 * mm, f"Cliente: {data.get('cliente', '-')}")
    c.drawRightString(PAGE_W - MARGIN, y_top - 18 * mm, f"Data: {data.get('data', '-')}")

    # (opzionale) se vuoi in futuro "Pagina X di Y":
    # if total_pages:
    #   c.drawRightString(PAGE_W - MARGIN, y_top - 8*mm, f"Pagina {page_no} di {total_pages}")


def draw_footer(c, data):
    y0 = MARGIN
    c.setFont(FONT, 9)
    c.drawString(MARGIN, y0 + 4 * mm, data.get("footer_left", "MITO Srl"))
    c.drawRightString(PAGE_W - MARGIN, y0 + 4 * mm, data.get("footer_right", "www.mito.it"))


def draw_table_header(c, x0, y):
    c.setFont(FONT_B, 10)
    x = x0
    for key, w in COLS:
        c.drawString(x + 2, y - 6 * mm, LABELS.get(key, key))
        x += w


def draw_row(c, x0, y, row):
    """
    Riga con descrizione multilinea. Ritorna l’altezza consumata.
    """
    c.setFont(FONT, FS)

    # Fallback chiavi (così i codici escono SEMPRE)
    cod = str(row.get("cod") or row.get("codice") or row.get("sku") or row.get("articolo") or "")
    descr = str(row.get("descr") or row.get("descrizione") or row.get("nome") or "")
    qty = str(row.get("qty") or row.get("quantita") or row.get("qta") or "")
    price = str(row.get("price") or row.get("prezzo") or "")
    total = str(row.get("total") or row.get("totale") or "")

    # Wrap descrizione dentro la colonna "descr"
    descr_col_w = dict(COLS)["descr"] - 6  # padding
    descr_lines = wrap_text(descr, FONT, FS, descr_col_w)
    descr_lines = descr_lines[:4]  # limite (stabilità)

    # Altezza riga variabile
    row_h = max(ROW_MIN_H, len(descr_lines) * LEADING + 3 * mm)

    # Baseline testo (prima riga)
    text_y = y - 5 * mm

    # COD
    x = x0
    c.drawString(x + 2, text_y, cod)
    x += dict(COLS)["cod"]

    # DESCR multiline
    for i, line in enumerate(descr_lines):
        c.drawString(x + 2, text_y - i * LEADING, line)
    x += dict(COLS)["descr"]

    # QTY/PRICE/TOTAL allineati a destra sulla prima riga
    c.drawRightString(x + dict(COLS)["qty"] - 2, text_y, qty)
    x += dict(COLS)["qty"]

    c.drawRightString(x + dict(COLS)["price"] - 2, text_y, price)
    x += dict(COLS)["price"]

    c.drawRightString(x + dict(COLS)["total"] - 2, text_y, total)

    return row_h


def paginate_rows(rows, y_start, y_bottom):
    """
    Spezza le righe per pagina considerando row_h variabile.
    Ritorna lista di pagine, ognuna lista righe.
    """
    pages = []
    idx = 0

    while idx < len(rows):
        y = y_start
        page_rows = []

        # spazio per intestazione tabella
        y -= TABLE_HEADER_H

        while idx < len(rows):
            r = rows[idx]
            descr = str(r.get("descr") or r.get("descrizione") or r.get("nome") or "")
            descr_w = dict(COLS)["descr"] - 6
            lines = wrap_text(descr, FONT, FS, descr_w)[:4]
            row_h = max(ROW_MIN_H, len(lines) * LEADING + 3 * mm)

            if y - row_h < y_bottom:
                break

            page_rows.append(r)
            y -= row_h
            idx += 1

        pages.append(page_rows)

    return pages


def build_pdf(payload: dict) -> bytes:
    rows = payload.get("rows", []) or []

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    body_top = PAGE_H - MARGIN - HEADER_H - GAP
    body_bottom = MARGIN + FOOTER_H + GAP

    x0 = MARGIN
    y_start = body_top

    pages = paginate_rows(rows, y_start, body_bottom)
    total_pages = max(1, len(pages))

    for i, page_rows in enumerate(pages, start=1):
        draw_header(c, payload, i, total_pages)
        draw_footer(c, payload)

        y = y_start
        draw_table_header(c, x0, y)
        y -= TABLE_HEADER_H

        for r in page_rows:
            rh = draw_row(c, x0, y, r)
            y -= rh

        if i < total_pages:
            c.showPage()

    c.save()
    return buf.getvalue()


class handler(BaseHTTPRequestHandler):
    def _send_pdf(self, pdf_bytes: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", 'inline; filename="preventivo.pdf"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(pdf_bytes)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = {}

        self._send_pdf(build_pdf(payload))

    def do_GET(self):
        # demo
        payload = {
            "doc_title": "PREVENTIVO P25-0069",
            "cliente": "CED (test)",
            "data": "18/12/2025",
            "footer_left": "MITO Srl",
            "footer_right": "www.mito.it",
            "rows": [
                {"codice": "CTR100", "descrizione": "CONTROTELAIO CLASSICO AU 800X2100 CART100 (CONFEZIONE 11PZ)", "quantita": 1, "prezzo": "1793", "totale": "1793"},
                {"codice": "DEA805", "descrizione": "INFERRIATA DEA PLATINO ANTA UNICA APRIBILE+SNODO L800 X H2100 CERNIERA", "quantita": 1, "prezzo": "805", "totale": "805"},
            ],
        }
        self._send_pdf(build_pdf(payload))
