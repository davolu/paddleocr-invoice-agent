"""Generate fictional Harmattan Supplies invoices and receipts, plus ground-truth JSON.

Every company, person, number, and account below is made up for a tutorial.
Run:  python src/generate_docs.py
"""
from __future__ import annotations

import io
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "data" / "docs"
GT = ROOT / "data" / "ground_truth"
DOCS.mkdir(parents=True, exist_ok=True)
GT.mkdir(parents=True, exist_ok=True)

FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
REG = FONT_DIR + "DejaVuSans.ttf"
BOLD = FONT_DIR + "DejaVuSans-Bold.ttf"
MONO = FONT_DIR + "DejaVuSansMono.ttf"
MONO_B = FONT_DIR + "DejaVuSansMono-Bold.ttf"

INK = (28, 28, 32)
GREY = (110, 110, 118)
ORANGE = (234, 88, 12)

VENDOR = "Harmattan Supplies Ltd"
VENDOR_LINES = [
    "14 Fictional Close, Yaba, Lagos",
    "RC DEMO-000000  |  hello@harmattan.example",
]


def f(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def money(x: float) -> str:
    return f"{x:,.2f}"


def totals(items, vat_rate=0.075):
    sub = round(sum(q * p for _, q, p in items), 2)
    tax = round(sub * vat_rate, 2)
    return sub, tax, round(sub + tax, 2)


def line_items_gt(items):
    return [
        {"description": d, "qty": q, "unit_price": p, "amount": round(q * p, 2)}
        for d, q, p in items
    ]


def draw_invoice(inv: dict, strike: dict | None = None, footer_note: str | None = None) -> Image.Image:
    W, H = 1240, 1754  # A4 at 150 dpi
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 14], fill=ORANGE)
    d.text((80, 70), VENDOR, font=f(BOLD, 44), fill=INK)
    for i, line in enumerate(VENDOR_LINES):
        d.text((80, 130 + i * 32), line, font=f(REG, 22), fill=GREY)
    d.text((W - 80, 70), "INVOICE", font=f(BOLD, 52), fill=ORANGE, anchor="ra")
    meta = [
        ("Invoice No:", inv["invoice_number"]),
        ("Invoice Date:", inv["date_text"]),
        ("Due Date:", inv["due_text"]),
    ]
    for i, (k, v) in enumerate(meta):
        y = 150 + i * 36
        d.text((W - 560, y), k, font=f(REG, 24), fill=GREY)
        d.text((W - 80, y), v, font=f(BOLD, 24), fill=INK, anchor="ra")

    d.text((80, 300), "BILL TO", font=f(BOLD, 22), fill=ORANGE)
    for i, line in enumerate(inv["bill_to"]):
        d.text((80, 336 + i * 32), line, font=f(BOLD if i == 0 else REG, 26 if i == 0 else 22), fill=INK)

    # table
    y0 = 500
    cols = [80, 700, 820, 1010]  # desc, qty, unit, amount (right edges for numbers)
    d.rectangle([60, y0, W - 60, y0 + 54], fill=(245, 245, 243))
    d.text((cols[0], y0 + 14), "Description", font=f(BOLD, 24), fill=INK)
    d.text((cols[1] + 60, y0 + 14), "Qty", font=f(BOLD, 24), fill=INK, anchor="ra")
    d.text((cols[2] + 160, y0 + 14), "Unit Price", font=f(BOLD, 24), fill=INK, anchor="ra")
    d.text((W - 80, y0 + 14), "Amount", font=f(BOLD, 24), fill=INK, anchor="ra")
    y = y0 + 74
    for idx, (desc, q, p) in enumerate(inv["items"]):
        d.text((cols[0], y), desc, font=f(REG, 24), fill=INK)
        d.text((cols[1] + 60, y), str(q), font=f(REG, 24), fill=INK, anchor="ra")
        if strike and strike["row"] == idx:
            old = money(strike["old_price"])
            ox = cols[2] + 160
            bbox = d.textbbox((ox, y - 26), old, font=f(REG, 20), anchor="ra")
            d.text((ox, y - 26), old, font=f(REG, 20), fill=GREY, anchor="ra")
            mid = (bbox[1] + bbox[3]) // 2
            d.line([bbox[0] - 2, mid, bbox[2] + 2, mid], fill=(200, 30, 30), width=3)
        d.text((cols[2] + 160, y), money(p), font=f(REG, 24), fill=INK, anchor="ra")
        d.text((W - 80, y), money(q * p), font=f(REG, 24), fill=INK, anchor="ra")
        y += 58
        d.line([60, y - 14, W - 60, y - 14], fill=(228, 228, 226), width=1)

    sub, tax, tot = totals(inv["items"])
    y += 20
    for k, v, bold in [
        ("Subtotal", money(sub), False),
        ("VAT (7.5%)", money(tax), False),
        ("Total (NGN)", money(tot), True),
    ]:
        d.text((W - 560, y), k, font=f(BOLD if bold else REG, 28 if bold else 24), fill=INK)
        d.text((W - 80, y), v, font=f(BOLD if bold else REG, 28 if bold else 24), fill=INK, anchor="ra")
        y += 46

    y = max(y + 40, 1400)
    d.text((80, y), "Payment: bank transfer to DEMO BANK, account 0000000000 (fictional).", font=f(REG, 22), fill=GREY)
    if footer_note:
        d.text((80, y + 40), footer_note, font=f(REG, 20), fill=GREY)
    d.text((80, H - 80), "Fictional sample document made for a tutorial. Not a real invoice.", font=f(REG, 18), fill=GREY)
    return im


def scanify(im: Image.Image, seed: int = 7) -> Image.Image:
    rnd = random.Random(seed)
    g = im.convert("L")
    g = g.rotate(1.6, resample=Image.BICUBIC, expand=True, fillcolor=255)
    # paper tint + speckle noise
    px = g.load()
    w, h = g.size
    for _ in range(int(w * h * 0.004)):
        x, y = rnd.randrange(w), rnd.randrange(h)
        px[x, y] = rnd.randrange(120, 200)
    g = g.filter(ImageFilter.GaussianBlur(0.7))
    rgb = Image.merge("RGB", (g.point(lambda v: int(v * 0.97 + 4)), g.point(lambda v: int(v * 0.95 + 6)), g.point(lambda v: int(v * 0.90 + 10))))
    rgb = rgb.resize((int(w * 0.8), int(h * 0.8)), Image.BILINEAR)
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=38)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def draw_receipt(r: dict) -> Image.Image:
    W = 560
    lines = []
    lines.append(("center_b", VENDOR.upper()))
    lines.append(("center", "Yaba Counter, Lagos"))
    lines.append(("center", "-" * 34))
    lines.append(("lr", ("Receipt:", r["receipt_number"])))
    lines.append(("lr", ("Date:", r["date_text"])))
    lines.append(("lr", ("Time:", r["time"])))
    lines.append(("center", "-" * 34))
    for desc, q, p in r["items"]:
        lines.append(("l", desc))
        lines.append(("lr", (f"  {q} x {money(p)}", money(q * p))))
    lines.append(("center", "-" * 34))
    sub, tax, tot = totals(r["items"])
    lines.append(("lr", ("SUBTOTAL", money(sub))))
    lines.append(("lr", ("VAT 7.5%", money(tax))))
    lines.append(("lr_b", ("TOTAL NGN", money(tot))))
    lines.append(("lr", ("PAID CARD ****0000", money(tot))))
    lines.append(("center", "-" * 34))
    lines.append(("center", "Thank you! Fictional demo."))
    H = 60 + len(lines) * 36 + 40
    im = Image.new("RGB", (W, H), (252, 251, 246))
    d = ImageDraw.Draw(im)
    y = 40
    for kind, val in lines:
        if kind.startswith("center"):
            d.text((W // 2, y), val, font=f(MONO_B if kind.endswith("_b") else MONO, 22), fill=INK, anchor="ma")
        elif kind == "l":
            d.text((30, y), val, font=f(MONO, 22), fill=INK)
        else:
            a, b = val
            fnt = f(MONO_B if kind.endswith("_b") else MONO, 22)
            d.text((30, y), a, font=fnt, fill=INK)
            d.text((W - 30, y), b, font=fnt, fill=INK, anchor="ra")
        y += 36
    # faint thermal fade
    im = im.filter(ImageFilter.GaussianBlur(0.4))
    return im


def save_gt(name: str, gt: dict) -> None:
    (GT / f"{name}.json").write_text(json.dumps(gt, indent=2) + "\n")


def invoice_gt(inv: dict, extra: dict | None = None) -> dict:
    sub, tax, tot = totals(inv["items"])
    gt = {
        "doc_type": "invoice",
        "vendor": VENDOR,
        "invoice_number": inv["invoice_number"],
        "invoice_date": inv["date_iso"],
        "due_date": inv["due_iso"],
        "bill_to": inv["bill_to"][0],
        "currency": "NGN",
        "line_items": line_items_gt(inv["items"]),
        "subtotal": sub,
        "tax": tax,
        "total": tot,
    }
    if extra:
        gt.update(extra)
    return gt


def main() -> None:
    clean = {
        "invoice_number": "HS-INV-2026-0417",
        "date_text": "18 Nov 2026",
        "date_iso": "2026-11-18",
        "due_text": "02 Dec 2026",
        "due_iso": "2026-12-02",
        "bill_to": ["Ikoyi Design Studio", "Attn: Accounts", "7 Example Road, Ikoyi, Lagos"],
        "items": [
            ("A4 Copier Paper (box of 5 reams)", 6, 18500.00),
            ("Black Toner Cartridge TN-2420", 2, 42750.00),
            ("Ergonomic Office Chair", 1, 165000.00),
            ("Whiteboard Markers (pack of 12)", 4, 6200.00),
        ],
    }
    im = draw_invoice(clean)
    im.save(DOCS / "invoice_clean.png")
    im.save(DOCS / "invoice_clean.pdf", "PDF", resolution=150)
    save_gt("invoice_clean", invoice_gt(clean))

    scanify(im).save(DOCS / "invoice_scan.jpg", quality=95)
    save_gt("invoice_scan", invoice_gt(clean))

    table = {
        "invoice_number": "HS-INV-2026-0452",
        "date_text": "21 Nov 2026",
        "date_iso": "2026-11-21",
        "due_text": "05 Dec 2026",
        "due_iso": "2026-12-05",
        "bill_to": ["Lekki Coding Academy", "Attn: Operations", "22 Sample Avenue, Lekki, Lagos"],
        "items": [
            ("USB-C Docking Station", 5, 38900.00),
            ("27-inch Monitor", 5, 189500.00),
            ("Wireless Keyboard and Mouse Set", 10, 15400.00),
            ("HDMI Cable 2m", 12, 3250.00),
            ("Laptop Stand, Aluminium", 10, 11800.00),
            ("Surge Protector, 6-way", 6, 9750.00),
            ("Noise-cancelling Headset", 4, 47600.00),
            ("Cable Ties (bag of 100)", 3, 1450.00),
        ],
    }
    draw_invoice(table).save(DOCS / "invoice_table.png")
    save_gt("invoice_table", invoice_gt(table))

    receipt = {
        "receipt_number": "YC-88213",
        "date_text": "23/11/2026",
        "date_iso": "2026-11-23",
        "time": "14:37",
        "items": [
            ("Sticky Notes 3x3", 3, 1200.00),
            ("Gel Pen, Blue (10)", 2, 2650.00),
            ("Stapler, Heavy Duty", 1, 7800.00),
            ("Box Files A4", 4, 1900.00),
        ],
    }
    draw_receipt(receipt).save(DOCS / "receipt_thermal.png")
    sub, tax, tot = totals(receipt["items"])
    save_gt(
        "receipt_thermal",
        {
            "doc_type": "receipt",
            "vendor": VENDOR,
            "receipt_number": receipt["receipt_number"],
            "invoice_date": receipt["date_iso"],
            "currency": "NGN",
            "line_items": line_items_gt(receipt["items"]),
            "subtotal": sub,
            "tax": tax,
            "total": tot,
        },
    )

    gotcha = {
        "invoice_number": "HS-INV-2026-0468",
        "date_text": "24 Nov 2026",
        "date_iso": "2026-11-24",
        "due_text": "08 Dec 2026",
        "due_iso": "2026-12-08",
        "bill_to": ["Surulere Print Hub", "Attn: Mrs. A. Example", "3 Placeholder Street, Surulere, Lagos"],
        "items": [
            ("Laminating Pouches A4 (100)", 5, 8400.00),
            ("Paper Guillotine A3", 1, 54000.00),  # corrected price; old crossed-out price 61,500.00
            ("Binding Combs 10mm (100)", 3, 5300.00),
        ],
    }
    note = "Early payment: 2% discount if paid in full by 05 Dec 2026."
    draw_invoice(gotcha, strike={"row": 1, "old_price": 61500.00}, footer_note=note).save(DOCS / "invoice_gotcha.png")
    save_gt(
        "invoice_gotcha",
        invoice_gt(
            gotcha,
            {"early_payment_discount": {"percent": 2, "pay_by": "2026-12-05"}},
        ),
    )
    for p in sorted(DOCS.iterdir()):
        print(p.name, p.stat().st_size)


if __name__ == "__main__":
    main()
