# DataCleaner — Enterprise PII Scrubbing CLI

**Scrub Personally Identifiable Information from database dumps, CSVs, and documents — without breaking your data.**

---

## One-Liner

```bash
dc scrub-dump production_export.csv --level external
# → 148,182 cells anonymized. JOINs still work. BI still renders. Zero cloud calls.
```

---

## The Problem

Every company has databases full of customer PII. When you need to:

- Share data with a third-party vendor
- Pass GDPR/HIPAA/CCPA compliance audits
- Give developers a realistic test dataset
- Publish anonymized research

...you face a choice: **redact everything and break your data**, or **risk leaking PII**.

Most tools pick one. DataCleaner does both.

---

## What Makes DataCleaner Different

### Deterministic Hashing — JOINs Survive

Most anonymizers generate random fake values. That breaks referential integrity:

```
patients.email = "anon_a1b2@test"        ← random
appointments.contact = "anon_c3d4@test"   ← different random

Result: JOIN queries return garbage. BI dashboards break.
```

DataCleaner uses SHA-256 deterministic hashing:

```
patients.email = sarah@acme.com       → anon_d9ca@scrubbed.local
appointments.contact = sarah@acme.com → anon_d9ca@scrubbed.local
                                         ↑ IDENTICAL. JOIN works.
```

No mapping table. No sync service. Just math.

### Three Privacy Levels, One Command

| Mode | Level | What It Does | Use Case |
|------|-------|-------------|----------|
| **External** | L3 Full Scrub | SHA-256 irreversible anonymization. Sensitive free-text columns deleted. | Public datasets, compliance audits, third-party sharing |
| **Internal** | L1 Partial Mask | Business-readable masking. Names show first characters, emails reveal domain, SSNs show last 4. | Customer support, internal dashboards, cross-team analytics |
| **Admin** | L2 Tokenization | AES-256-GCM encrypted tokens. Fully recoverable with master password. | Test databases, CEO access, internal development |

```bash
dc scrub-dump employees.csv --level external     # Public release
dc scrub-dump employees.csv --level internal     # Internal teams
dc scrub-dump employees.csv --level admin --password "MyKey"  # Recoverable
dc recover employees_scrubbed.csv --password "MyKey"           # Restore
```

---

## Features

### Detection Engine
- **50+ regex patterns** — emails, phones (US/UK/EU/CN), credit cards, SSN, IBAN, passports, IPs, API keys
- **35 column-name patterns** — auto-detects PII columns by header name
- **Content sampling** — classifies unlabeled columns by scanning cell values
- **LLM pass** (Pro/Team) — catches names, addresses, medical info in free text

### Masking Engine (L0–L4)
- **L0 Preserve** — keep as-is
- **L1 Partial** — show edges, mask middle (business-readable)
- **L2 Tokenize** — AES-256-GCM recoverable with password
- **L3 Full Scrub** — SHA-256 deterministic, irreversible
- **L4 Delete** — remove column entirely

### Format Preservation
- Phone numbers still look like phone numbers
- SSNs keep XXX-XX-XXXX format
- Credit cards preserve card structure
- BI dashboards and ETL pipelines keep working

### Security
- **100% local processing** — zero data leaves your machine
- **Offline license validation** — no phone-home
- **No telemetry, no analytics, no cloud APIs**
- **GDPR / HIPAA / CCPA / ISO 27001 audit log generation**
- Audit logs record what was scrubbed — never store actual PII values

### Formats Supported
CSV, SQL dumps (INSERT statements), JSON (array of objects), PDF, DOCX, XLSX, TXT, MD, HTML, XML, LOG, EML

### Performance
- Streaming mode for files >100MB (chunked at 10K rows)
- Parallel multi-file processing (Pro/Team)
- Regex pass: instant. LLM pass: local GPU speed.

---

## Pricing

| Tier | Price | Includes |
|------|-------|----------|
| **Pro** | $149 one-time | Full LLM detection, deterministic hashing, all 3 masking modes, AES-256 recovery, all formats, parallel processing, year 1 updates |
| **Team** | $399 one-time (5 seats) | Everything in Pro + custom PII patterns, Docker image, priority support |

**Optional renewal:** $49/year (Pro) or $99/year (Team) for continued updates after year 1. License never expires — keep using your purchased version forever.

---

## System Requirements

- **OS:** Windows 10+, macOS 12+, Linux (x86_64)
- **Python:** 3.10+ (bundled in installer)
- **GPU:** Optional — NVIDIA GPU recommended for LLM pass. Regex pass runs on CPU.
- **Internet:** Not required after installation (offline license validation)

---

## What's Included

- `dc` CLI executable (single binary)
- AES-256 vault encryption for recoverable mode
- Audit log generator (GDPR/HIPAA ready)
- 5 masking levels with column auto-detection
- 174 automated tests verified per release

---

## Who Is This For?

- **Engineering teams** shipping anonymized test data to QA
- **Compliance officers** preparing GDPR/HIPAA audit artifacts
- **Data analysts** sharing scrubbed datasets with external vendors
- **CTOs** who need a deterministic, JOIN-safe anonymization pipeline
- **Startups** that can't afford enterprise DLP tools but need real PII protection

---

## Proven

- 174 automated tests passing per release
- 110 PII cells scrubbed from 10-record demo in under 2 seconds
- 14/14 field recovery verified (admin mode round-trip)
- Zero false positives on non-PII columns (employee_id, department, start_date)

---

## Get It Now

1. Purchase your license (Pro or Team)
2. Download the installer
3. Run `dc license activate <your-key>`
4. Start scrubbing: `dc scrub-dump your_data.csv --level external`

**Questions?** contact@getdatacleaner.com
