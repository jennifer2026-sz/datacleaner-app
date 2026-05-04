# 🔒 DataCleaner CLI

**Deterministic Data Reconstruction — Scrubbed Data That Still Works**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Powered by Ollama](https://img.shields.io/badge/powered-Ollama-orange.svg)](https://ollama.ai)
[![GPU: Local](https://img.shields.io/badge/GPU-Local%20RTX-purple.svg)]()
[![Tests: 148/148](https://img.shields.io/badge/tests-148%2F148-brightgreen.svg)]()

---

## 🎯 What It Does

DataCleaner doesn't just **erase** sensitive data — it **reconstructs** it.
Scrubbed emails, phones, and IDs stay **consistent across tables**.
Your JOINs still work. Your BI dashboards still render. Your test suite still passes.

Everything runs **entirely on your machine** — no cloud, no API calls, no data leakage.

```bash
$ dc scrub-dump production_export.csv

  Scrubbing dump: production_export.csv
  Format: csv | Style: placeholder
  Rows: 50,000 | Columns: 18

  Phase 1: Classifying columns...
  email      SENSITIVE  email
  phone      SENSITIVE  phone_us
  ssn        SENSITIVE  ssn
  name       clean      -

  Phase 2: Scrubbing 3 sensitive column(s)...
  ✓ email: 50,000 cells scrubbed
  ✓ phone: 49,872 cells scrubbed
  ✓ ssn: 48,310 cells scrubbed

  ╭──────────────────────────────────╮
  │ ✓ Scrubbing complete             │
  │   50,000 rows × 18 columns       │
  │   3 sensitive columns found      │
  │   148,182 cells anonymized        │
  │   Output: production_scrubbed.csv │
  ╰──────────────────────────────────╯
```

## 🧠 The Key Difference: Why "Scrubbed" ≠ "Broken"

Most anonymization tools generate **random** fake values. This destroys referential integrity:

```
patients.email = "anon_a1b2@test"     ← random
appointments.contact = "anon_c3d4@test" ← different random value

Result: JOIN queries on patient_id return garbage.
```

**DataCleaner uses SHA-256 deterministic hashing:**
Same input → same fake output. Every time. Across every table. Across every run.

```
patients.email = j@real.com → anon_b4f6@scrubbed.local
appointments.contact = j@real.com → anon_b4f6@scrubbed.local
                               ↑ IDENTICAL. JOIN works. BI works.
```

No mapping table to maintain. No sync service to run. Just math.

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

### Common Workflows

```bash
# Scan a single file (regex only, zero cost)
dc scan document.pdf --no-llm

# Deep scan with local LLM (catches names, addresses, context)
dc scan ./contracts/ --redact -o ./clean/

# Scrub a database dump (CSV, SQL, JSON)
dc scrub-dump production_backup.csv -o safe_data.csv

# Scrub with format-preserving anonymization
dc scrub-dump users.json --style placeholder

# View audit history
dc audit

# Check license status
dc license status
```

## 📋 Supported Formats

| Format | Extensions | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | Text + scanned (PyMuPDF) |
| Word | `.docx` | Tables included |
| Excel | `.xlsx`, `.xls` | All sheets |
| CSV | `.csv` | Auto-detects encoding |
| JSON | `.json` | Array of objects |
| SQL Dump | `.sql` | INSERT statements |
| Plain text | `.txt`, `.md`, `.xml`, `.html`, `.log` | UTF-8/GBK/Latin-1 |

## 🔍 What It Detects

### Regex Pass (instant, 50+ patterns)
- ✉️ Email addresses
- 📱 Phone numbers (US, UK, EU, China)
- 💳 Credit card numbers (Visa, MC, Amex, Discover)
- 🆔 SSN, National Insurance, China ID
- 🏦 IBAN, SWIFT/BIC codes
- 🌐 IPv4, IPv6 addresses
- 🔑 API keys, tokens, passwords
- 📍 US ZIP, UK Postcode

### LLM Pass (contextual, requires Ollama)
- 👤 Person names in natural text
- 🏠 Physical addresses and PO boxes
- 🏥 Medical information and conditions
- 💰 Salary figures with context
- 👨‍👩‍👧 Family member names
- 🚗 License plates, VIN numbers
- 🔐 Internal URLs and credentials

## 💰 Pricing

| Tier | Price | What You Get |
|------|-------|--------------|
| **Free** | $0 | `dc scan` (regex), audit logs, CSV/JSON/SQL formats |
| **Pro** | $99 one-time | `dc scrub-dump`, full LLM scanning, deterministic anonymization, API access |
| **Team** | $299 one-time | Everything in Pro + 10 seats, custom patterns, priority support |

[Get a License →](https://getdatacleaner.com/#pricing)

## 🛡️ Privacy & Security

DataCleaner is **local-first by design**:
- ✅ All processing happens on your machine
- ✅ Zero telemetry or analytics
- ✅ No network calls (even license validation is offline)
- ✅ Audit logs stored locally — **never contain actual PII values**
- ✅ SHA-256 deterministic hashing — no mapping table to leak
- ✅ GDPR-friendly: you remain the sole data controller

[Read the full Privacy Policy →](https://getdatacleaner.com/privacy)

## 🏗️ For Developers

```python
from datacleaner.scanner import scan_text
from datacleaner.redactor import redact_text
from datacleaner.commands.scrub_dump import scrub_dump

# Scan text
result = scan_text("Contact John Smith at john@example.com", use_llm=True)
print(f"Found {result['stats']['total']} PII instances")

# Redact
clean = redact_text("Contact John Smith at john@example.com",
                     result['findings'], style="block")
print(clean)  # "Contact [REDACTED] at [REDACTED]"

# Scrub a database dump programmatically
stats = scrub_dump("production.csv", output_path="clean.csv")
print(f"Scrubbed {stats['total_cells_scrubbed']} cells across {len(stats['sensitive_columns'])} columns")
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

- [x] `dc scrub-dump` — deterministic database dump anonymization
- [ ] Streaming mode for large files (>100MB)
- [ ] Custom PII pattern editor
- [ ] Batch processing with parallel workers
- [ ] PostgreSQL pg_dump direct integration
- [ ] Docker image for server deployments
- [ ] Integration plugins (n8n, Zapier, Make.com)

## 📄 License

MIT License — see [LICENSE](LICENSE).

Pro and Team tiers use a commercial license addendum. See [EULA](https://getdatacleaner.com/eula).

---

**Made by Jeam | Powered by local GPUs everywhere | Scrubbed data that still works**
