import json
from io import BytesIO
from http.server import BaseHTTPRequestHandler

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import ImageReader

PAGE_W, PAGE_H = A4

# ---- Layout ----
MARGIN = 12 * mm
GAP = 4 * mm

HEADER_H = 62 * mm   # header “ricco” come template
FOOTER_H = 12 * mm

# Colori (simili al template)
C_GREEN_BG = colors.HexColor("#EEF7D8")
C_GREEN_BORDER = colors.HexColor("#BFD7A8")
C_GREY_HDR = colors.HexColor("#E5E7EB")
C_TEXT = colors.HexColor("#111827")
C_MUTED = colors.HexColor("#6B7280")

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"

# Tabella stile template
# CODICE | DESCRIZIONE | Q.TÀ | U.M. | PREZZO | SCONTO | IMPORTO
COLS = [
    ("codice", 30 * mm),
    ("descrizione", 78 * mm),
    ("qty", 12 * mm),
    ("um", 12 * mm),
    ("prezzo", 20 * mm),
    ("sconto", 18 * mm),
    ("importo", 20 * mm),
]
LABELS = {
    "codice": "CODICE",
    "descrizione": "DESCRIZIONE",
    "qty": "Q.TÀ",
    "um": "U.M.",
    "prezzo": "PREZZO",
    "sconto": "SCONTO",
    "importo": "IMPORTO",
}

TABLE_HDR_H = 8 * mm
ROW_MIN_H = 8 * mm
LEADING = 4.2 * mm  # interlinea descrizione
FS = 8.8


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


def draw_logo(c, logo_data_uri, x, y, w, h):
    """
    logo_data_uri: "data:image/png;base64,...." (opzionale)
    """
    if not logo_data_uri or not isinstance(logo_data_uri, str) or "base64," not in logo_data_uri:
        # fallback: scritta MITO
        c.setFont(FONT_B, 26)
        c.setFillColor(C_TEXT)
        c.drawString(x, y + 2*mm, "MITO")
        return

    try:
        import base64
        b64 = logo_data_uri.split("base64,", 1)[1]
        img_bytes = base64.b64decode(b64)
        img = ImageReader(BytesIO(img_bytes))
        c.drawImage(img, x, y, width=w, height=h, mask="auto")
    except Exception:
        c.setFont(FONT_B, 26)
        c.setFillColor(C_TEXT)
        c.drawString(x, y + 2*mm, "MITO")


def draw_top_header(c, data):
    """
    Riproduce blocco alto: logo + PREVENTIVO + riga sotto + “PREVENTIVO N° … DEL …”
    """
    y_top = PAGE_H - MARGIN

    # Logo a sinistra
    draw_logo(c, data.get("logo_data_uri"), MARGIN, y_top - 22*mm, 36*mm, 14*mm)

    # Titolo grande “PREVENTIVO”
    c.setFillColor(C_TEXT)
    c.setFont(FONT_B, 16)
    c.drawString(MARGIN + 52*mm, y_top - 12*mm, "PREVENTIVO")

    # Linea sottile
    c.setStrokeColor(C_MUTED)
    c.setLineWidth(0.6)
    c.line(MARGIN, y_top - 26*mm, PAGE_W - MARGIN, y_top - 26*mm)

    # Riga “PREVENTIVO N° … DEL …”
    c.setFont(FONT_B, 10.5)
    num = data.get("numero", "") or ""
    data_doc = data.get("data_doc", "") or data.get("data", "") or ""
    if num and data_doc:
        subtitle = f"PREVENTIVO N° {num} DEL {data_doc}"
    elif num:
        subtitle = f"PREVENTIVO N° {num}"
    else:
        subtitle = "PREVENTIVO"
    c.drawString(MARGIN, y_top - 34*mm, subtitle)


def draw_boxes(c, data):
    """
    Due box verdi come template:
    - Destinatario / Destinazione Merce
    - Riferimento / Agente / Pagamento
    """
    y_top = PAGE_H - MARGIN - 38*mm

    box_w = PAGE_W - 2*MARGIN

    # ---- BOX 1 (Destinatario / Destinazione) ----
    b1_h = 26*mm
    c.setFillColor(C_GREEN_BG)
    c.setStrokeColor(C_GREEN_BORDER)
    c.roundRect(MARGIN, y_top - b1_h, box_w, b1_h, 3*mm, stroke=1, fill=1)

    c.setFillColor(C_TEXT)
    c.setFont(FONT_B, 9)
    c.drawString(MARGIN + 5*mm, y_top - 6*mm, "Destinatario")
    c.drawString(MARGIN + box_w/2 + 5*mm, y_top - 6*mm, "Destinazione Merce")

    c.setFont(FONT, 8.6)
    # colonne testo
    left_x = MARGIN + 5*mm
    right_x = MARGIN + box_w/2 + 5*mm
    base_y = y_top - 11*mm

    destinatario = data.get("destinatario", {}) or {}
    destinazione = data.get("destinazione", {}) or {}

    # sinistra
    lines_left = [
        destinatario.get("ragsoc", "") or "",
        destinatario.get("indirizzo", "") or "",
        destinatario.get("cap_citta", "") or "",
        f"Conto: {destinatario.get('conto','')}".strip() if destinatario.get("conto") else "",
        f"P.IVA: {destinatario.get('piva','')}".strip() if destinatario.get("piva") else "",
        f"Tel.: {destinatario.get('tel','')}".strip() if destinatario.get("tel") else "",
        f"Email: {destinatario.get('email','')}".strip() if destinatario.get("email") else "",
    ]
    # destra (destinazione merce)
    lines_right = [
        destinazione.get("ragsoc", "") or "",
        destinazione.get("indirizzo", "") or "",
        destinazione.get("cap_citta", "") or "",
    ]

    # stampa compatta
    yy = base_y
    for t in [x for x in lines_left if x]:
        c.drawString(left_x, yy, t)
        yy -= 4.0*mm

    yy = base_y
    for t in [x for x in lines_right if x]:
        c.drawString(right_x, yy, t)
        yy -= 4.0*mm

    # ---- BOX 2 (Riferimento / Agente / Pagamento) ----
    y2_top = y_top - b1_h - 6*mm
    b2_h = 16*mm
    c.setFillColor(C_GREEN_BG)
    c.setStrokeColor(C_GREEN_BORDER)
    c.roundRect(MARGIN, y2_top - b2_h, box_w, b2_h, 3*mm, stroke=1, fill=1)

    c.setFillColor(C_TEXT)
    c.setFont(FONT_B, 8.6)

    rows = [
        ("Riferimento Preventivo:", data.get("riferimento", "")),
        ("Agente di riferimento:", data.get("agente", "")),
        ("Pagamento:", data.get("pagamento", "")),
    ]

    label_x = MARGIN + 5*mm
    value_x = MARGIN + 48*mm
    yy = y2_top - 5.3*mm
    c.setFont(FONT_B, 8.6)
    for lab, val in rows:
        c.drawString(label_x, yy, lab)
        c.setFont(FONT, 8.6)
        c.drawString(value_x, yy, (val or ""))
        c.setFont(FONT_B, 8.6)
        yy -= 5.0*mm


def draw_footer(c, data, page_no, total_pages):
    y0 = MARGIN
    c.setFont(FONT, 7.8)
    c.setFillColor(C_MUTED)

    footer_line = data.get(
        "footer_line",
        "MITO Srl · Via del Lavoro, Tavullia (PU) · P.IVA IT01352930414 · Tel. 0721/476320 · www.mito.it · info@mito.it",
    )

    c.drawString(MARGIN, y0 + 4*mm, footer_line)

    c.setFillColor(C_MUTED)
    c.drawRightString(PAGE_W - MARGIN, y0 + 4*mm, f"Pagina {page_no} di {total_pages}")
    c.setFillColor(C_TEXT)


def draw_table_header(c, x0, y):
    # barra grigia
    c.setFillColor(C_GREY_HDR)
    c.setStrokeColor(C_GREY_HDR)
    c.rect(x0, y - TABLE_HDR_H, PAGE_W - 2*MARGIN, TABLE_HDR_H, stroke=0, fill=1)

    c.setFillColor(C_TEXT)
    c.setFont(FONT_B, 8.2)

    x = x0
    for key, w in COLS:
        c.drawString(x + 2, y - 5.6*mm, LABELS.get(key, key))
        x += w


def row_height_for(r):
    descr = str(r.get("descrizione") or r.get("descr") or r.get("nome") or "")
    descr_w = dict(COLS)["descrizione"] - 6
    lines = wrap_text(descr, FONT, FS, descr_w)[:4]
    return max(ROW_MIN_H, len(lines) * LEADING + 3*mm)


def draw_row(c, x0, y, r):
    """
    Ritorna altezza consumata.
    """
    c.setFont(FONT, FS)
    c.setFillColor(C_TEXT)

    # Fallback chiavi (così CODICE non resta vuoto)
    codice = str(r.get("codice") or r.get("cod") or r.get("sku") or r.get("articolo") or "")
    descr = str(r.get("descrizione") or r.get("descr") or r.get("nome") or "")
    qty = str(r.get("quantita") or r.get("qty") or r.get("qta") or "")
    um = str(r.get("um") or r.get("u_m") or r.get("unita") or r.get("unit") or "nr")
    prezzo = str(r.get("prezzo") or r.get("price") or "")
    sconto = str(r.get("sconto") or r.get("discount") or "")
    importo = str(r.get("importo") or r.get("totale") or r.get("total") or "")

    descr_w = dict(COLS)["descrizione"] - 6
    descr_lines = wrap_text(descr, FONT, FS, descr_w)[:4]
    rh = max(ROW_MIN_H, len(descr_lines) * LEADING + 3*mm)

    # separatore riga
    c.setStrokeColor(colors.HexColor("#E5E7EB"))
    c.setLineWidth(0.6)
    c.line(x0, y - rh, PAGE_W - MARGIN, y - rh)

    # baseline
    text_y = y - 5.2*mm

    x = x0
    # CODICE
    c.drawString(x + 2, text_y, codice); x += dict(COLS)["codice"]

    # DESCR multiline
    for i, line in enumerate(descr_lines):
        c.drawString(x + 2, text_y - i*LEADING, line)
    x += dict(COLS)["descrizione"]

    # QTY / UM / PREZZO / SCONTO / IMPORTO (destra)
    c.drawRightString(x + dict(COLS)["qty"] - 2, text_y, qty); x += dict(COLS)["qty"]
    c.drawString(x + 2, text_y, um); x += dict(COLS)["um"]
    c.drawRightString(x + dict(COLS)["prezzo"] - 2, text_y, prezzo); x += dict(COLS)["prezzo"]
    c.drawRightString(x + dict(COLS)["sconto"] - 2, text_y, sconto); x += dict(COLS)["sconto"]
    c.drawRightString(x + dict(COLS)["importo"] - 2, text_y, importo)

    return rh


def paginate_rows(rows, y_start, y_bottom):
    pages = []
    idx = 0

    while idx < len(rows):
        y = y_start

        # spazio header tabella
        y -= TABLE_HDR_H

        page_rows = []
        while idx < len(rows):
            rh = row_height_for(rows[idx])
            if y - rh < y_bottom:
                break
            page_rows.append(rows[idx])
            y -= rh
            idx += 1

        pages.append(page_rows)

    return pages if pages else [[]]


def draw_totals_box(c, data, x_right, y_bottom):
    """
    Box totali verde chiaro in basso a destra come template (ultima pagina).
    """
    totals = data.get("totali", {}) or {}

    lines = [
        ("Imponibile Articoli", totals.get("imponibile_articoli", "")),
        ("Spese di trasporto", totals.get("trasporto", "")),
        ("Totale Imponibile", totals.get("totale_imponibile", "")),
        ("Totale IVA compresa", totals.get("totale_iva", "")),
    ]

    box_w = 62*mm
    box_h = 24*mm
    x = x_right - box_w
    y = y_bottom + 6*mm

    c.setFillColor(C_GREEN_BG)
    c.setStrokeColor(C_GREEN_BORDER)
    c.roundRect(x, y, box_w, box_h, 3*mm, stroke=1, fill=1)

    c.setFont(FONT, 8.2)
    c.setFillColor(C_TEXT)

    yy = y + box_h - 6*mm
    for i, (lab, val) in enumerate(lines):
        c.setFillColor(C_MUTED if i < 2 else C_TEXT)
        c.drawString(x + 5*mm, yy, lab)
        c.setFont(FONT_B if i >= 2 else FONT, 8.2)
        c.drawRightString(x + box_w - 5*mm, yy, str(val or ""))
        c.setFont(FONT, 8.2)
        yy -= 5.3*mm

    c.setFillColor(C_TEXT)


def build_pdf(payload: dict) -> bytes:
    rows = payload.get("rows", []) or []

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # area contenuto
    body_top = PAGE_H - MARGIN - HEADER_H - GAP
    body_bottom = MARGIN + FOOTER_H + GAP
    x0 = MARGIN
    y_start = body_top

    pages = paginate_rows(rows, y_start, body_bottom)
    total_pages = max(1, len(pages))

    for page_no, page_rows in enumerate(pages, start=1):
        # Header grafico (uguale su tutte le pagine)
        draw_top_header(c, payload)

        # Box verdi SOLO pagina 1 (come template)
        if page_no == 1:
            draw_boxes(c, payload)

        # Footer (tutte)
        draw_footer(c, payload, page_no, total_pages)

        # Tabella
        # se pagina 1, tabella scende sotto i box
        y_table_top = y_start
        if page_no == 1:
            y_table_top = PAGE_H - MARGIN - (HEADER_H - 10*mm) - 40*mm  # posizionamento sotto box

        draw_table_header(c, x0, y_table_top)
        y = y_table_top - TABLE_HDR_H

        for r in page_rows:
            rh = draw_row(c, x0, y, r)
            y -= rh

        # Totali box SOLO ultima pagina (come template)
        if page_no == total_pages:
            draw_totals_box(c, payload, PAGE_W - MARGIN, body_bottom)

        # Note: se vuoi pagina note separata, inviale come payload.notes_page = True
        if page_no < total_pages:
            c.showPage()

    c.save()
    return buf.getvalue()


class handler(BaseHTTPRequestHandler):
    def _send_pdf(self, pdf_bytes: bytes, filename="preventivo.pdf"):
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'inline; filename="{filename}"')
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

        filename = (payload.get("filename") or "preventivo.pdf")
        self._send_pdf(build_pdf(payload), filename=filename)

    def do_GET(self):
        # demo rapida
        payload = {
            "numero": "P25-0069",
            "data_doc": "18/12/2025",
            "doc_title": "PREVENTIVO",
            "destinatario": {
                "ragsoc": "CED (test)",
                "indirizzo": "Via del Lavoro snc",
                "cap_citta": "61010 Tavullia (PU)",
                "conto": "600010005",
                "piva": "IT123456",
                "tel": "0721476320",
                "email": "ced@mito.it",
            },
            "destinazione": {"ragsoc": "IDEM"},
            "riferimento": "Prova nota ordine",
            "agente": "Agente Test Mito - Tel. 0721476320 · Email agente@mito.it",
            "pagamento": "R.B.60 Gg Df Fm esc.Ago/Dic",
            "totali": {
                "imponibile_articoli": "3104,55 €",
                "trasporto": "103,00 €",
                "totale_imponibile": "3207,55 €",
                "totale_iva": "3913,21 €",
            },
            "rows": [
                {"codice":"CO0800410021C", "descrizione":"CONTROTELAIO CLASSICO AU 800X2100 CART100 (CONFEZIONE 11PZ)", "quantita":"1", "um":"nr", "prezzo":"1793,00 €", "sconto":"50,5%", "importo":"887,54 €"},
                {"codice":"DP0406053000", "descrizione":"INFERRIATA DEA PLATINO ANTA UNICA APRIBILE+SNODO L800 X H2100 CERNIERA BILICO", "quantita":"1", "um":"nr", "prezzo":"805,00 €", "sconto":"38%", "importo":"499,10 €"},
            ],
        }
        self._send_pdf(build_pdf(payload), filename="preventivo-demo.pdf")
