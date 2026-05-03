# 🔒 DataCleaner CLI

**Local AI-Powered PII Detection & Redaction — Zero Data Leaves Your Machine**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Powered by Ollama](https://img.shields.io/badge/powered-Ollama-orange.svg)](https://ollama.ai)
[![GPU: Local](https://img.shields.io/badge/GPU-Local%20RTX-purple.svg)]()

---

## 🎯 What It Does

DataCleaner scans your documents for Personally Identifiable Information (PII)
**entirely on your machine** — no cloud, no API calls, no data leakage.

```bash
$ dc scan contracts/ --redact

  Scanning 3 file(s)
  LLM: qwen3.5:9b | Style: block

  ✓ contracts/client_agreement.pdf     47 findings   CONTACT(23) IDENTITY(15) FINANCIAL(9)
  ✓ contracts/employee_data.csv        128 findings  CONTACT(89) IDENTITY(31) FINANCIAL(8)
  ✓ contracts/notes.txt                12 findings   CONTACT(7) PERSON_NAME(5)

  Applying redactions...
  ✓ contracts/redacted/client_agreement_redacted.pdf
    Audit: ~/.datacleaner/audit/audit_client_agreement_20260502.json
```

## 🧠 How It Works

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Document     │ ──▶ │  Pass 1: Regex    │ ──▶ │  Pass 2: LLM  │
│  (PDF/CSV/   │     │  Email, Phone,    │     │  Contextual   │
│   DOCX/TXT)  │     │  SSN, Credit Card │     │  Names, Addr  │
└──────────────┘     └──────────────────┘     └──────┬───────┘
                                                      │
                                          ┌───────────▼───────────┐
                                          │  Redacted Output      │
                                          │  + Compliance Audit   │
                                          └───────────────────────┘
```

Two-pass detection:
1. **Regex (fast)**: Emails, phones, SSN, credit cards, IPs, API keys — 50+ patterns
2. **LLM (deep)**: Contextual PII regex misses — names in prose, addresses in
   paragraphs, medical data, family relationships

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) with a model (recommended: `qwen3.5:9b`)
- NVIDIA GPU recommended (works on CPU too, just slower)

### Install

```bash
# Install Ollama and pull a model
ollama serve
ollama pull qwen3.5:9b

# Install DataCleaner
pip install datacleaner

# Or from source
git clone https://github.com/jennifer2026-sz/datacleaner-app.git
cd datacleaner-cli
pip install -e .
```

### First Scan

```bash
# Quick scan (regex only)
dc scan document.pdf --no-llm

# Deep scan with local LLM
dc scan document.pdf

# Scan and redact
dc scan ./documents/ --redact -o ./clean/

# Different redaction style
dc scan file.csv --redact --style placeholder
```

## 📋 Supported Formats

| Format | Extensions | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | Text + scanned (PyMuPDF) |
| Word | `.docx` | Tables included |
| Excel | `.xlsx`, `.xls` | All sheets |
| CSV | `.csv` | Auto-detects encoding |
| Plain text | `.txt`, `.md`, `.json`, `.xml`, `.html`, `.log` | UTF-8/GBK/Latin-1 |

## 🔍 What It Detects

### Regex Pass (instant)
- ✉️ Email addresses
- 📱 Phone numbers (US, UK, EU, China)
- 💳 Credit card numbers (Visa, MC, Amex, Discover)
- 🆔 SSN, National Insurance, China ID
- 🏦 IBAN, SWIFT/BIC codes
- 🌐 IPv4, IPv6 addresses
- 🔑 API keys, tokens, passwords

### LLM Pass (contextual, requires Ollama)
- 👤 Person names in natural text
- 🏠 Physical addresses and PO boxes
- 🏥 Medical information and conditions
- 💰 Salary figures with context
- 👨‍👩‍👧 Family member names
- 🚗 License plates, VIN numbers
- 🔐 Internal URLs and credentials

## 💰 Pricing

| Tier | Price | Limits |
|------|-------|--------|
| **Free** | $0 | 100 docs/month, regex full, LLM limited to 500 chars |
| **Pro** | $49/month | Unlimited documents, full LLM scanning, API access |
| **Team** | $199/month | Everything in Pro + 10 users, custom patterns, SSO |

[Get a License →](https://getdatacleaner.com/#pricing)

## 🛡️ Privacy & Security

DataCleaner is **local-first by design**:
- ✅ All processing happens on your machine
- ✅ Zero telemetry or analytics
- ✅ No network calls (even license validation is offline)
- ✅ Audit logs stored locally (never contain actual PII values)
- ✅ GDPR-friendly: you remain the sole data controller

[Read the full Privacy Policy →](PRIVACY.md)

## 🏗️ For Developers

```python
from datacleaner.scanner import scan_text
from datacleaner.redactor import redact_text

# Scan text
result = scan_text("Contact John Smith at john@example.com", use_llm=True)
print(f"Found {result['stats']['total']} PII instances")

# Redact
clean = redact_text("Contact John Smith at john@example.com",
                     result['findings'], style="block")
print(clean)  # "Contact [REDACTED] at [REDACTED]"
```

## 📊 Compliance

DataCleaner generates audit logs suitable for:
- **GDPR** Article 30 (Records of Processing Activities)
- **HIPAA** audit trail requirements
- **CCPA** data inventory
- **ISO 27001** information security management

Each audit log records: timestamp, file, finding categories, detection methods,
and confidence scores — **without ever storing the actual PII values**.

## 🗺️ Roadmap

- [ ] Streaming mode for large files (>100MB)
- [ ] Custom PII pattern editor
- [ ] Batch processing with parallel workers
- [ ] Structured output for databases (SQL INSERT with redactions)
- [ ] Docker image for server deployments
- [ ] Integration plugins (n8n, Zapier, Make.com)

## 📄 License

MIT License — see [LICENSE](LICENSE).

Pro and Team tiers use a commercial license addendum. See [EULA](EULA.md).

---

**Made with ❤️ by Jeam | Powered by local GPUs everywhere**
