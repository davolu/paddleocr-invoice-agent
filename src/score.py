"""Score against ground truth.

Two modes:
  python src/score.py --ocr               # is each true value even present in the OCR text?
  python src/score.py --model claude-sonnet-5-5   # did the agent's JSON get each field right?
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GT_DIR = ROOT / "data" / "ground_truth"
SCALARS = ["vendor", "invoice_number", "receipt_number", "invoice_date", "due_date", "bill_to", "currency", "subtotal", "tax", "total"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def flatten(gt: dict) -> dict[str, object]:
    """Ground truth as a flat {field_path: value} dict."""
    flat = {k: gt[k] for k in SCALARS if gt.get(k) is not None}
    for i, it in enumerate(gt.get("line_items", [])):
        for k in ("description", "qty", "unit_price", "amount"):
            flat[f"line_items[{i}].{k}"] = it[k]
    if gt.get("early_payment_discount"):
        flat["early_payment_discount.percent"] = gt["early_payment_discount"]["percent"]
        flat["early_payment_discount.pay_by"] = gt["early_payment_discount"]["pay_by"]
    return flat


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def to_num(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(re.sub(r"[^\d.\-]", "", str(v)))
    except ValueError:
        return None


def ocr_forms(field: str, v) -> list[str]:
    """How a true value would look printed on the page."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if field.endswith(".qty") or field.endswith(".percent"):
            return [str(int(v))]
        return [f"{v:,.2f}"]
    s = str(v)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = m.groups()
        return [f"{d} {MONTHS[int(mo) - 1]} {y}", f"{d}/{mo}/{y}"]
    return [s]


def get_path(obj: dict, path: str):
    cur = obj
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        if part.startswith("["):
            idx = int(part[1:-1])
            if not isinstance(cur, list) or idx >= len(cur):
                return None
            cur = cur[idx]
        else:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
    return cur


def match(true, pred) -> bool:
    if pred is None:
        return False
    if isinstance(true, (int, float)) and not isinstance(true, bool):
        p = to_num(pred)
        return p is not None and abs(p - float(true)) < 0.005
    return norm_text(true) == norm_text(pred)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--tier", default="medium")
    ap.add_argument("--model")
    args = ap.parse_args()

    total_hit = total_n = 0
    report = {}
    for gt_path in sorted(GT_DIR.glob("*.json")):
        stem = gt_path.stem
        flat = flatten(json.loads(gt_path.read_text()))
        misses = []
        if args.ocr:
            text = norm_text((ROOT / "outputs" / "ocr" / args.tier / f"{stem}.txt").read_text())
            for k, v in flat.items():
                if not any(norm_text(f) in text for f in ocr_forms(k, v)):
                    misses.append(k)
        else:
            pred = json.loads((ROOT / "outputs" / "extracted" / args.model / f"{stem}.json").read_text())
            for k, v in flat.items():
                if not match(v, get_path(pred, k)):
                    misses.append(f"{k}: want {v!r}, got {get_path(pred, k)!r}")
        hit = len(flat) - len(misses)
        total_hit += hit
        total_n += len(flat)
        report[stem] = {"matched": hit, "fields": len(flat), "misses": misses}
        print(f"{stem:18s} {hit:3d}/{len(flat):<3d} fields")
        for m in misses:
            print(f"    miss  {m}")
    print(f"{'ALL':18s} {total_hit:3d}/{total_n:<3d} fields ({100 * total_hit / total_n:.1f}%)")
    name = f"ocr_presence_{args.tier}" if args.ocr else f"extraction_{args.model}"
    out = ROOT / "outputs" / "scores"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps({"total_matched": total_hit, "total_fields": total_n, "docs": report}, indent=2))


if __name__ == "__main__":
    main()
