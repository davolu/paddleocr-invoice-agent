"""OCR text in, structured JSON out, using an Anthropic Claude model.

The model only sees PaddleOCR's text (not the image), so this shows what an agent
can do once OCR has made the page readable.

Needs ANTHROPIC_API_KEY in the environment (never printed or committed).
Run:  python src/extract_agent.py                       # all docs, medium-tier OCR text
      CLAUDE_MODEL=claude-haiku-5-5 python src/extract_agent.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
# Model used on recording day (25 Nov 2026). Any current Claude model id works here.
DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
API = "https://api.anthropic.com/v1/messages"

SCHEMA_HINT = {
    "doc_type": "invoice | receipt",
    "vendor": "string",
    "invoice_number": "string or null (invoices)",
    "receipt_number": "string or null (receipts)",
    "invoice_date": "YYYY-MM-DD (the document date)",
    "due_date": "YYYY-MM-DD or null",
    "bill_to": "customer company name or null",
    "currency": "ISO code, e.g. NGN",
    "line_items": [{"description": "string", "qty": "number", "unit_price": "number", "amount": "number"}],
    "subtotal": "number",
    "tax": "number",
    "total": "number",
    "early_payment_discount": "{percent: number, pay_by: YYYY-MM-DD} or null",
}

PROMPT = """You are a careful accounts-payable assistant.
Below is OCR text from one scanned business document. Lines are grouped left-to-right, top-to-bottom,
so table columns may be split across lines.

Return ONLY a JSON object with exactly these keys:
{schema}

Rules:
- Use only facts present in the text. If a field is not present, use null. Never invent values.
- Numbers are plain numbers without commas or currency symbols.
- If a price appears crossed out and replaced, use the price that the line amount actually uses.
- Include an early-payment discount only if the text states one.

OCR TEXT:
<<<
{text}
>>>"""


def call_claude(text: str, model: str) -> tuple[dict, dict]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY is not set (check with: test -n \"$ANTHROPIC_API_KEY\" && echo set)")
    body = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": PROMPT.format(schema=json.dumps(SCHEMA_HINT, indent=1), text=text)}],
    }
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    r = requests.post(API, headers=headers, json=body, timeout=120)
    if r.status_code != 200:
        # never echo headers; an error body does not contain the key
        sys.exit(f"Anthropic API error {r.status_code}: {r.text[:400]}")
    data = r.json()
    out = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text").strip()
    # tolerate a ```json fence, then parse the first {...} object
    out = out[out.find("{"): out.rfind("}") + 1]
    return json.loads(out), data.get("usage", {})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="medium")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--docs", nargs="*", default=None)
    args = ap.parse_args()

    ocr_dir = ROOT / "outputs" / "ocr" / args.tier
    out_dir = ROOT / "outputs" / "extracted" / args.model
    out_dir.mkdir(parents=True, exist_ok=True)
    stems = args.docs or sorted(p.stem for p in (ROOT / "data" / "ground_truth").glob("*.json"))
    usage_log = {}
    for stem in stems:
        text = (ocr_dir / f"{stem}.txt").read_text()
        t0 = time.perf_counter()
        result, usage = call_claude(text, args.model)
        secs = time.perf_counter() - t0
        (out_dir / f"{stem}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        usage_log[stem] = {"seconds": round(secs, 2), "usage": usage}
        print(f"[{stem}] extracted in {secs:.2f}s  tokens in/out: {usage.get('input_tokens')}/{usage.get('output_tokens')}")
        time.sleep(1)  # be gentle with rate limits
    (out_dir / "usage.json").write_text(json.dumps(usage_log, indent=2))


if __name__ == "__main__":
    main()
