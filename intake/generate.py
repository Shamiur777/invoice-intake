"""Generate synthetic invoices (PDF) plus ground truth. All vendors and data are fictional."""
import json
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

VENDORS = [
    "Northwind Supplies Pty Ltd", "Bluegum Office Solutions", "Harbour Print & Pack",
    "Delta Cloud Services LLC", "Maple Street Catering", "Riverbend Logistics",
    "Pioneer Stationery Co", "Lotus Digital Studio", "Summit IT Support", "Greenfield Cleaning Services",
]
ITEMS = [
    ("A4 copy paper (box)", 18.5), ("Toner cartridge", 64.0), ("Cloud hosting (monthly)", 120.0),
    ("Consulting hour", 95.0), ("Courier delivery", 12.75), ("Office chair", 210.0),
    ("Printing - flyers (100)", 42.0), ("Catering per head", 15.5), ("Software licence", 79.0),
    ("Cleaning service (visit)", 55.0),
]
CURRENCIES = {"USD": "$", "AUD": "A$", "BDT": "BDT "}
TAX_RATES = {"USD": 0.0, "AUD": 0.10, "BDT": 0.15}


def money(v: float, template: int, cur: str) -> str:
    s = f"{v:,.2f}"
    return {0: f"{cur} {s}", 1: f"{CURRENCIES[cur]}{s}", 2: s}[template]


def fmt_date(d: date, template: int) -> str:
    return [d.strftime("%Y-%m-%d"), d.strftime("%d %b %Y"), d.strftime("%d/%m/%Y")][template]


def make_invoice(rng: random.Random, idx: int) -> dict:
    cur = rng.choice(list(CURRENCIES))
    items = []
    for desc, price in rng.sample(ITEMS, rng.randint(1, 5)):
        qty = rng.randint(1, 12)
        items.append({"description": desc, "quantity": qty, "unit_price": price, "amount": round(qty * price, 2)})
    subtotal = round(sum(i["amount"] for i in items), 2)
    tax = round(subtotal * TAX_RATES[cur], 2)
    d = date(2026, 1, 1) + timedelta(days=rng.randint(0, 270))
    return {
        "vendor": rng.choice(VENDORS),
        "invoice_number": f"INV-{rng.randint(1000, 9999)}-{idx:03d}",
        "invoice_date": d.isoformat(),
        "currency": cur,
        "subtotal": subtotal,
        "tax": tax,
        "total": round(subtotal + tax, 2),
        "line_items": items,
    }


def render(inv: dict, path: Path, template: int) -> None:
    """Templates 0-2 use labels the baseline knows. Template 3 uses unfamiliar wording."""
    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    cur = inv["currency"]
    d = date.fromisoformat(inv["invoice_date"])
    y = h - 60
    c.setFont("Helvetica-Bold", 16)
    if template == 3:
        c.drawString(50, y, "Bill from:")
        y -= 20
    c.drawString(50, y, inv["vendor"])
    c.setFont("Helvetica", 10)
    labels = [("Invoice No: ", "Date: "), ("INVOICE # ", "Issued: "), ("Ref ", "Invoice date "),
              ("Document no. ", "Dated ")][template]
    style = template if template < 3 else 1
    y -= 30
    c.drawString(50, y, labels[0] + inv["invoice_number"])
    y -= 15
    c.drawString(50, y, labels[1] + fmt_date(d, style))
    if template == 2:
        y -= 15
        c.drawString(50, y, f"All amounts in {cur}")
    y -= 40
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Description")
    c.drawString(300, y, "Qty")
    c.drawString(350, y, "Unit price" if template != 2 else "Rate")
    c.drawString(450, y, "Amount")
    c.setFont("Helvetica", 10)
    for it in inv["line_items"]:
        y -= 18
        c.drawString(50, y, it["description"])
        c.drawString(300, y, str(it["quantity"]))
        c.drawString(350, y, money(it["unit_price"], style, cur))
        c.drawString(450, y, money(it["amount"], style, cur))
    y -= 40
    totals = [("Subtotal", "Tax", "Total Due"), ("Sub-total", "VAT/GST", "Total"), ("Net", "Tax", "Amount Due"),
              ("Items total", "Levy", "Payable")][template]
    rows = [(totals[0], inv["subtotal"])]
    if inv["tax"] > 0:  # some invoices show no tax line at all
        rows.append((totals[1], inv["tax"]))
    rows.append((totals[2], inv["total"]))
    for label, val in rows:
        c.drawString(350, y, label)
        c.drawString(450, y, money(val, style, cur))
        y -= 16
    c.save()


def generate(out_dir: Path, n: int = 50, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    truth = []
    for i in range(1, n + 1):
        inv = make_invoice(rng, i)
        template = rng.randint(0, 2)
        name = f"invoice_{i:03d}.pdf"
        render(inv, out_dir / name, template)
        truth.append({"file": name, "template": template, **inv})
    (out_dir / "ground_truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    return truth


def rasterize(pdf_path: Path, rng: random.Random) -> None:
    """Turn a PDF into an image-only PDF with slight rotation and noise, like a phone scan."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageFilter

    page = pdfium.PdfDocument(str(pdf_path))[0]
    img = page.render(scale=1.6).to_pil().convert("L")
    img = img.rotate(rng.uniform(-1.5, 1.5), expand=False, fillcolor=255)
    noise = Image.effect_noise(img.size, 18)
    img = Image.blend(img, noise, 0.08).filter(ImageFilter.GaussianBlur(0.6)).convert("RGB")
    img.save(pdf_path, "PDF", resolution=110)


def generate_hard(out_dir: Path, n: int = 20, seed: int = 11) -> list[dict]:
    """Harder set: first half are scan-like image PDFs (no text layer), second half use unfamiliar labels."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    truth = []
    for i in range(1, n + 1):
        inv = make_invoice(rng, 500 + i)
        scanned = i <= n // 2
        template = rng.randint(0, 2) if scanned else 3
        name = f"hard_{i:03d}.pdf"
        render(inv, out_dir / name, template)
        if scanned:
            rasterize(out_dir / name, rng)
        truth.append({"file": name, "template": template, "scanned": scanned, **inv})
    (out_dir / "ground_truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    return truth


if __name__ == "__main__":
    t = generate(Path("data/invoices"))
    print(f"Generated {len(t)} standard invoices in data/invoices")
    h = generate_hard(Path("data/hard"))
    print(f"Generated {len(h)} hard invoices in data/hard (10 scan-like, 10 unfamiliar labels)")
