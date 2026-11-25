"""Run PaddleOCR (PP-OCRv6, CPU) on the sample documents.

Saves plain text, raw JSON, a visualisation, and wall-clock timings to outputs/ocr/.
Run:  python src/ocr_engine.py            (default tier: medium)
      python src/ocr_engine.py --tier small
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "data" / "docs"


def build_ocr(tier: str):
    from paddleocr import PaddleOCR

    kwargs = dict(
        device="cpu",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    if tier != "medium":  # medium is the 3.7.0 default
        kwargs["text_detection_model_name"] = f"PP-OCRv6_{tier}_det"
        kwargs["text_recognition_model_name"] = f"PP-OCRv6_{tier}_rec"
    return PaddleOCR(**kwargs)


def ocr_lines(result) -> list[dict]:
    """Turn one PaddleOCR result into simple lines: text, score, box (top-left y,x)."""
    r = result.json["res"] if hasattr(result, "json") else result["res"]
    out = []
    for text, score, box in zip(r["rec_texts"], r["rec_scores"], r["rec_boxes"]):
        out.append({"text": text, "score": round(float(score), 4), "box": [int(v) for v in box]})
    return out


def reading_order_text(lines: list[dict], row_tol: int = 14) -> str:
    """Group boxes into rows by y, then left-to-right, so tables read like rows."""
    rows: list[list[dict]] = []
    for ln in sorted(lines, key=lambda l: (l["box"][1], l["box"][0])):
        cy = (ln["box"][1] + ln["box"][3]) / 2
        for row in rows:
            rcy = sum((x["box"][1] + x["box"][3]) / 2 for x in row) / len(row)
            if abs(cy - rcy) <= row_tol:
                row.append(ln)
                break
        else:
            rows.append([ln])
    return "\n".join("   ".join(x["text"] for x in sorted(r, key=lambda l: l["box"][0])) for r in rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="medium", choices=["tiny", "small", "medium"])
    ap.add_argument("--docs", nargs="*", default=None)
    args = ap.parse_args()

    out_dir = ROOT / "outputs" / "ocr" / args.tier
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    ocr = build_ocr(args.tier)
    init_s = time.perf_counter() - t0
    print(f"[init] PP-OCRv6 {args.tier} on CPU ready in {init_s:.2f}s")

    paths = [DOCS / d for d in args.docs] if args.docs else sorted(
        p for p in DOCS.iterdir() if p.suffix.lower() in {".png", ".jpg"}
    )
    timings = {"tier": args.tier, "init_s": round(init_s, 2), "docs": {}}
    for p in paths:
        t1 = time.perf_counter()
        results = ocr.predict(str(p))
        secs = time.perf_counter() - t1
        res = results[0]
        lines = ocr_lines(res)
        text = reading_order_text(lines)
        stem = p.stem
        res.save_to_img(str(out_dir))
        (out_dir / f"{stem}.lines.json").write_text(json.dumps(lines, indent=1, ensure_ascii=False))
        (out_dir / f"{stem}.txt").write_text(text + "\n")
        mean = sum(l["score"] for l in lines) / max(1, len(lines))
        timings["docs"][stem] = {"seconds": round(secs, 2), "lines": len(lines), "mean_score": round(mean, 4)}
        print(f"[{stem}] {len(lines)} text lines, mean confidence {mean:.3f}, {secs:.2f}s")
    (out_dir / "timings.json").write_text(json.dumps(timings, indent=2))


if __name__ == "__main__":
    main()
