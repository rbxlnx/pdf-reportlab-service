import json
from io import BytesIO
from http.server import BaseHTTPRequestHandler

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth


PAGE_W, PAGE_H = A4

# Margini & blocchi
MARGIN = 12 * mm
HEADER_H = 46 * mm     # header più alto (stile “vecchio”)
FOOTER_H = 14 * mm
GAP = 4 * mm

# Tabella
TABLE_HEADER_H = 8 * mm
ROW_MIN_H = 8 * mm
LEADING = 4.2 * mm     # interlinea testo descrizione

# Colonne
COLS = [
    ("cod", 25 * mm),
    ("descr", 95 * mm),
    ("qty", 15 * mm),
    ("price", 25 * mm),
    ("total", 25 * mm),
]
LABELS = {"cod": "Cod.", "descr": "Descrizione", "qty": "Q.tà", "price": "Prezzo", "total": "Totale"}

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"
FS = 9


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

    # Fascia colorata (stile istituzionale)
    band_h = 14 * mm
    c.setFillColor(colors.HexColor("#111827"))  # blu notte / quasi nero
    c.rect(0, y_top - band_h, PAGE_W, band_h, stroke=0, fill=1)

    # Titolo + pagine (bianco)
    c.setFillColor(colors.white)
    c.setFont(FONT_B, 12)
    c.drawString(x0, y_top - 10 * mm, data.get("doc_title", "PREVENTIVO"))
    c.setFont(FONT, 9)
    if total_pages:
        c.drawRightString(PAGE_W - MARGIN, y_top - 10 * mm, f"Pagina {page_no} di {total_pages}")
    else:
        c.drawRightString(PAGE_W - MARGIN, y_top - 10 * mm, f"Pagina {page_no}")

    # Ritorno nero
    c.setFillColor(colors.black)

    # Box cliente (sotto fascia)
    box_y_top = y_top - band_h - 2 * mm
    box_h = 26 * mm
    c.setStrokeColor(colors.HexColor("#E5E7EB"))
    c.setFillColor(colors.HexColor("#F9FAFB"))
    c.rect(x0, box_y_top - box_h, PAGE_W - 2 * MARGIN, box_h, stroke=1, fill=1)

    c.setFillColor(colors.black)
    c.setFont(FONT_B, 9)
    c.drawString(x0 + 4 * mm, box_y_top - 6 * mm, "Destinatario")
    c.setFont(FONT, 9)

    cliente = data.get("cliente", "-")
    data_doc = data.get("data", "-")

    c.drawString(x0 + 4 * mm, box_y_top - 12 * mm, f"{cliente}")
    c.drawRightString(PAGE_W - MARGIN - 4 * mm, box_y_top - 12 * mm, f"Data: {data_doc}")

    # Riga info opzionali
    info_left = data.get("header_left_info", "")
    info_right = data.get("header_right_info", "")
    if info_left:
        c.drawString(x0 + 4 * mm, box_y_top - 18 * mm, info_left)
    if info_right:
        c.drawRightString(PAGE_W - MARGIN - 4 * mm, box_y_top - 18 * mm, info_right)


def draw_footer(c, data, page_no, total_pages):
    y0 = MARGIN
    c.setFont(FONT, 8)
    c.setFillColor(colors.HexColor("#4B5563"))
    c.drawString(MARGIN, y0 + 6 * mm, data.get("footer_left", "MITO Srl"))
    c.drawRightString(PAGE_W - MARGIN, y0 + 6 * mm, data.get("footer_right", "www.mito.it"))

    # Paginazione in footer (stile “vecchio”)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawRightString(PAGE_W - MARGIN, y0 + 2 * mm, f"Pagina {page_no} di {total_pages}")
    c.setFillColor(colors.black)


def draw_table_header(c, x0, y):
    # sfondo header tabella
    c.setFillColor(colors.HexColor("#EEF2FF"))
    c.setStrokeColor(colors.HexColor("#E5E7EB"))
    c.rect(x0, y - TABLE_HEADER_H + 1 * mm, PAGE_W - 2 * MARGIN, TABLE_HEADER_H, stroke=1, fill=1)

    c.setFillColor(colors.HexColor("#111827"))
    c.setFont(FONT_B, 9)

    x = x0
    for key, w in COLS:
        c.drawString(x + 2, y - 5 * mm, LABELS.get(key, key))
        x += w

    c.setFillColor(colors.black)


def draw_row(c, x0, y, row):
    """
    Disegna riga con descrizione multilinea.
    Ritorna l'altezza effettiva consumata (per paginazione).
    """
    c.setFont(FONT, FS)

    # fallback chiavi (così i codici ESCOGNO SEMPRE)
    cod = str(row.get("cod") or row.get("codice") or row.get("sku") or row.get("articolo") or "")
    descr = str(row.get("descr") or row.get("descrizione") or row.get("nome") or "")
    qty = str(row.get("qty") or row.get("quantita") or row.get("qta") or "")
    price = str(row.get("price") or row.get("prezzo") or "")
    total = str(row.get("total") or row.get("totale") or "")

    # wrap descrizione
    descr_col_w = dict(COLS)["descr"] - 6  # padding
    descr_lines = wrap_text(descr, FONT, FS, descr_col_w)
    descr_lines = descr_lines[:4]  # limite per stabilità layout

    row_h = max(ROW_MIN_H, len(descr_lines) * LEADING + 3 * mm)

    # linea separatore riga (leggera)
    c.setStrokeColor(colors.HexColor("#E5E7EB"))
    c.line(x0, y - row_h, PAGE_W - MARGIN, y - row_h)
    c.setStrokeColor(colors.black)

    # baseline testo
    text_y = y - 5 * mm

    # COD
    x = x0
    c.drawString(x + 2, text_y, cod)
    x += dict(COLS)["cod"]

    # DESCR multiline
    for i, line in enumerate(descr_lines):
        c.drawString(x + 2, text_y - i * LEADING, line)
    x += dict(COLS)["descr"]

    # QTY, PRICE, TOTAL (allineati a destra sulla prima riga)
    c.drawRightString(x + dict(COLS)["qty"] - 2, text_y, qty)
    x += dict(COLS)["qty"]

    c.drawRightString(x + dict(COLS)["price"] - 2, text_y, price)
    x += dict(COLS)["price"]

    c.drawRightString(x + dict(COLS)["total"] - 2, text_y, total)

    return row_h


def paginate_rows(rows, y_start, y_bottom):
    """
    Spezza le righe per pagina usando row_h variabile:
    ritorna lista pagine, ognuna è lista righe.
    """
    pages = []
    idx = 0

    while idx < len(rows):
        y = y_start
        page_rows = []

        # header tabella consuma spazio
        y -= TABLE_HEADER_H

        while idx < len(rows):
            # stimiamo altezza riga in base alla descrizione (stesso criterio di draw_row)
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
        draw_footer(c, payload, i, total_pages)

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
        self.send_header("Content-Disposition", 'inline; filename="documento.pdf"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(pdf_bytes)

    def do_GET(self):
        # PDF demo
        payload = {
            "doc_title": "TEST REPORTLAB",
            "cliente": "Rossi Srl",
            "data": "19/12/2025",
            "footer_left": "MITO Srl",
            "footer_right": "www.mito.it",
            "rows": [
                {"codice": "A001", "descrizione": "Descrizione molto lunga che deve andare a capo senza invadere le colonne successive.", "quantita": 1, "prezzo": "€ 100,00", "totale": "€ 100,00"},
                {"codice": "A002", "descrizione": "Seconda riga con descrizione ancora più lunga, per testare il wrapping su più righe della stessa cella.", "quantita": 2, "prezzo": "€ 50,00", "totale": "€ 100,00"},
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
