# PaddleOCR Invoice-Reading Agent

Companion code for the Agentic AI Hub video **"Let's Build an Invoice-Reading AI Agent with PaddleOCR."**

An agent that reads invoices and receipts with [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) (Apache 2.0), turns the text into structured JSON with **Claude Sonnet 5.5** (`claude-sonnet-5-5`) through the Anthropic API, and is scored field by field against answers we already know.

All documents in `data/docs/` are **fictional** (Harmattan Supplies Ltd does not exist; every number and account is fake).

## What's inside

| Path | What it does |
|---|---|
| `src/generate_docs.py` | Builds 5 fictional documents and their ground-truth JSON |
| `src/ocr_engine.py` | Runs PaddleOCR (PP-OCRv6, CPU) and saves text, boxes, a visualisation and timings |
| `src/extract_agent.py` | Sends the OCR text (not the image) to a Claude model and saves structured JSON |
| `src/score.py` | `--ocr`: is each true value present in the OCR text? `--model`: did the agent put it in the right field? |
| `data/docs/`, `data/ground_truth/` | The sample documents and the correct answers |
| `outputs/` | Results from our recording-day run |

## Setup (CPU, no GPU needed)

Python 3.10 or 3.11 recommended.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
pip install -r requirements.txt
python -c "import paddle, paddleocr; print(paddle.__version__, paddleocr.__version__)"
```

## Run it

```bash
python src/generate_docs.py          # optional: the docs are already in data/docs/
python src/ocr_engine.py             # PP-OCRv6 medium on CPU; first run downloads ~133 MB of models
python src/score.py --ocr            # is every answer in the OCR text?

cp .env.example .env                 # add your Anthropic API key; never commit or print it
set -a && source .env && set +a
python src/extract_agent.py          # default model: claude-sonnet-5-5
python src/score.py --model claude-sonnet-5-5
```

To try another Claude model: `CLAUDE_MODEL=claude-haiku-5-5 python src/extract_agent.py`, then score with `--model claude-haiku-5-5`. API calls are billed by Anthropic; check current pricing first.

## Our results (recording day, 25 Nov 2026, 8-core CPU, no GPU)

PP-OCRv6 medium, models cached:

| Document | Text lines | Avg confidence | Time |
|---|---:|---:|---:|
| Clean invoice | 42 | 99.8% | 4.26 s |
| Tilted scan | 42 | 99.9% | 2.83 s |
| Table invoice | 58 | 99.8% | 3.91 s |
| Till receipt | 30 | 99.4% | 1.29 s |
| Tricky invoice | 40 | 99.8% | 3.80 s |

OCR presence check: **137 / 137** ground-truth fields appear in the OCR text.

Agent extraction with `claude-sonnet-5-5`: **137 / 137** fields matched (clean 25/25, tilted scan 25/25, table 41/41, receipt 23/23, tricky 23/23). Each call took 2.29–3.98 s with 731–968 input tokens and 409–750 output tokens (`outputs/extracted/claude-sonnet-5-5/`, `outputs/scores/`).

On the tricky invoice the agent used the corrected 54,000.00 unit price (not the crossed-out 61,500.00) and returned the 2% early-payment discount.

These are one run on five synthetic documents on one machine, not a benchmark. Real paperwork will be messier; add your own documents and ground truth to find the weak spots.

## Links

- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
- PaddleOCR docs: https://www.paddleocr.ai
- PaddleOCR MCP server docs: https://www.paddleocr.ai/latest/en/version3.x/integrations/mcp_server.html
- Anthropic API docs: https://docs.anthropic.com
