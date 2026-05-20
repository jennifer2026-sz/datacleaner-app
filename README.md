# 🔒 DataCleaner CLI

**5-Level PII Masking — Scrub Once, Share Three Ways**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/license-Source%20Available-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-174%2F174-brightgreen.svg)]()
[![GitHub stars](https://img.shields.io/github/stars/jennifer2026-sz/datacleaner-app?style=flat)]()

---

## What It Does

One CLI command, three different outputs — depending on who's looking at the data.

```bash
# Public release — full SHA-256 anonymization, irreversible
dc scrub-dump employees.csv --level external

# Internal teams — partial mask, business-readable
dc scrub-dump employees.csv --level internal

# CEO access — AES-256 tokenization, fully recoverable
dc scrub-dump employees.csv --level admin --password "master-key"
dc recover employees_scrubbed.csv --password "master-key"
```

Same employee record under each mode:

| Column | Original | External | Internal | Admin |
|--------|----------|----------|----------|-------|
| email | sarah@acme.com | `anon_d9ca@scrubbed.local` | `sar***@acmecorp.com` | `tok_c24c@masked.local` |
| phone | +1-415-555-0134 | `+1-555-34b8` | `+1--***-***` | `+1-555-37c8` |
| ssn | 529-37-4812 | `XXX-XX-2be3` | `***-**-4812` | `XXX-XX-d816` |
| salary | $95,000 | `[SCRUBBED]` | `$95,***` | `$95,000` |
| dept | Engineering | Engineering | Engineering | Engineering |

- **External** = irreversible, compliance-safe, JOIN-safe (SHA-256 deterministic)
- **Internal** = business-readable, partial mask, team-friendly
- **Admin** = tokenized, AES-256-GCM encrypted, recoverable with password

Everything runs **entirely on your machine** — no cloud, no API calls, no data leakage.

---

## Open Core vs Pro/Team

| Feature | Open Core | Pro ($149) | Team ($399) |
|---------|-----------|------------|-------------|
| Regex PII detection (50+ patterns) | ✅ | ✅ | ✅ |
| L0-L4 Tiered masking engine | ✅ | ✅ | ✅ |
| Deterministic SHA-256 hashing | ✅ | ✅ | ✅ |
| Database dump scrubbing (CSV/SQL/JSON) | ✅ | ✅ | ✅ |
| AES-256 admin mode + recovery | ✅ | ✅ | ✅ |
| Offline license validation | ✅ | ✅ | ✅ |
| LLM contextual detection | ❌ | ✅ | ✅ |
| PDF/DOCX/XLSX support | ❌ | ✅ | ✅ |
| Parallel batch processing | ❌ | ✅ | ✅ |
| Custom PII pattern editor | ❌ | ❌ | ✅ |
| Docker deployment image | ❌ | ❌ | ✅ |
| Priority support | ❌ | ❌ | ✅ |
| Commercial use license | ❌ | ✅ | ✅ |

👉 **[Buy Pro ($149) or Team ($399) on Gumroad](https://galaxycontent.gumroad.com/l/qhfjnh)**
One-time purchase. Perpetual license. Optional $49/year update renewal.

---

## Quick Start

### Install

```bash
git clone https://github.com/jennifer2026-sz/datacleaner-app.git
cd datacleaner-app
pip install -e .
```

### Scrub a CSV

```bash
dc scrub-dump production_export.csv --level external
```

```
  Scrubbing dump: production_export.csv
  Format: csv | Style: placeholder
  Rows: 50,000 | Columns: 18

  Phase 1: Classifying columns...
  email      SENSITIVE  email
  phone      SENSITIVE  phone_us
  ssn        SENSITIVE  ssn

  Phase 2: Scrubbing 3 sensitive column(s) (mode=external)...
  ✓ email: 50,000 cells scrubbed
  ✓ phone: 49,872 cells scrubbed
  ✓ ssn: 48,310 cells scrubbed

  ╭──────────────────────────────────╮
  │ ✓ Scrubbing complete             │
  │   50,000 rows × 18 columns       │
  │   3 sensitive columns found      │
  │   148,182 cells anonymized       │
  │   Output: production_scrubbed.csv │
  ╰──────────────────────────────────╯
```

### Activate Pro/Team License

```bash
dc license activate YOUR-LICENSE-KEY
```

Validation is fully offline — no phone-home, no internet required.

---

## Why Deterministic Hashing Matters

Most anonymization tools generate **random** fake values. This destroys referential integrity:

```
patients.email = "anon_a1b2@test"        ← random
appointments.contact = "anon_c3d4@test"   ← different random

Result: JOIN queries return garbage.
```

DataCleaner uses **SHA-256 deterministic hashing** — same input → same output, every time:

```
patients.email = sarah@acme.com       → anon_d9ca@scrubbed.local
appointments.contact = sarah@acme.com → anon_d9ca@scrubbed.local
                                         ↑ IDENTICAL. JOINs survive.
```

No mapping table. No sync service. Just math.

---

## PII Types Detected

### Regex Pass (instant, 50+ patterns)
Emails, Phones (US/UK/EU/CN), Credit Cards (Visa/MC/Amex/Discover), SSN, National Insurance, China ID, IBAN, SWIFT/BIC, IPv4/IPv6, API Keys, Tokens, ZIP/Postcode

### Column-Name Auto-Detection (35 patterns)
full_name, first_name, email, phone, ssn, credit_card, passport, salary, address, ip_address, dob, notes, comments, medical_history, bank_account, iban, swift, driver_license, and more

### LLM Pass (Pro/Team only, runs on local GPU)
Person names, physical addresses, medical conditions, salary figures, family member names, license plates, VIN numbers, internal URLs

---

## Supported Formats

| Format | Extensions |
|--------|-----------|
| CSV | `.csv` |
| SQL Dump | `.sql` |
| JSON | `.json` |
| PDF (Pro/Team) | `.pdf` |
| Word (Pro/Team) | `.docx` |
| Excel (Pro/Team) | `.xlsx`, `.xls` |
| Text | `.txt`, `.md`, `.xml`, `.html`, `.log` |

---

## Privacy & Security

- ✅ All processing on your machine — zero cloud calls
- ✅ Zero telemetry or analytics
- ✅ Offline license validation — no phone-home
- ✅ Audit logs never store actual PII values
- ✅ GDPR / HIPAA / CCPA / ISO 27001 compliant audit trails

---

## License

Source Available License — see [LICENSE](LICENSE).

Free for personal, educational, and evaluation use.
Commercial use requires a Pro or Team license from [getdatacleaner.com](https://getdatacleaner.com).
See [EULA](https://getdatacleaner.com/eula) for complete terms.

---

**Made by Jeam | Scrubbed data that still works**
