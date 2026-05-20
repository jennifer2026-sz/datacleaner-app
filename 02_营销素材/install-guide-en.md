# DataCleaner Installation Guide

**Version:** v0.2.0 | **Last Updated:** May 2026

---

## Quick Install (Recommended)

### Windows

1. Download `datacleaner-setup.exe` from your Gumroad purchase
2. Double-click to run the installer
3. Open **Command Prompt** or **PowerShell**
4. Verify installation:
   ```cmd
   dc --version
   ```
5. Activate your license:
   ```cmd
   dc license activate YOUR-LICENSE-KEY
   ```
6. Test it:
   ```cmd
   dc scrub-dump sample.csv --level external
   ```

### macOS

1. Download `datacleaner-0.2.0.pkg` from your Gumroad purchase
2. Double-click to install
3. Open **Terminal**
4. Verify:
   ```bash
   dc --version
   ```
5. Activate:
   ```bash
   dc license activate YOUR-LICENSE-KEY
   ```

### Linux

1. Download `datacleaner-0.2.0.tar.gz` from your Gumroad purchase
2. Extract and install:
   ```bash
   tar xzf datacleaner-0.2.0.tar.gz
   cd datacleaner-0.2.0
   ./install.sh
   ```
3. Activate:
   ```bash
   dc license activate YOUR-LICENSE-KEY
   ```

---

## Install from Source (Developers)

```bash
# Prerequisites
python3 --version  # Must be 3.10+

# Clone and install
git clone https://github.com/jennifer2026-sz/datacleaner-app.git
cd datacleaner-app
pip install -e .

# Verify
dc --version
```

---

## Quick Start

### 1. Scrub a CSV Database Dump

```bash
# External mode — for public release (irreversible)
dc scrub-dump employees.csv --level external

# Internal mode — for team sharing (business-readable)
dc scrub-dump employees.csv --level internal

# Admin mode — CEO access (recoverable with password)
dc scrub-dump employees.csv --level admin --password "YourSecretKey"
```

### 2. Recover Admin-Mode Data

```bash
dc recover employees_scrubbed.csv --password "YourSecretKey"
```

### 3. Scan Documents for PII

```bash
dc scan ./documents/ --no-llm          # Regex-only, instant
dc scan contract.pdf --redact          # Scan and redact
dc scan ./contracts/ --redact -o ./clean/  # Batch with output
```

### 4. View Audit Logs

```bash
dc audit
dc audit -n 20  # Last 20 entries
```

---

## Masking Levels Reference

| Level | Command Flag | Behavior | Recoverable |
|-------|-------------|----------|-------------|
| L0 | *(preserved columns)* | Keep original value | — |
| L1 | `--level internal` | Partial mask, business-readable | No |
| L2 | `--level admin --password KEY` | AES-256 tokenization | Yes (with password) |
| L3 | `--level external` | SHA-256 full scrub, deterministic | No |
| L4 | *(deleted columns)* | Remove column entirely | No |

### Example Output (Sarah Johnson — EMP001)

| Column | Original | External (L3) | Internal (L1) | Admin (L2) |
|--------|----------|---------------|---------------|------------|
| name | Sarah Johnson | [SCRUBBED:471c] | Sara********* | TOK_27d20dbc |
| email | sarah.j@acme.com | anon_d9ca@scrubbed.local | sar***@acmecorp.com | tok_c24c@masked.local |
| phone | +1-415-555-0134 | +1-555-34b8 | +1--***-*** | +1-555-37c8 |
| ssn | 529-37-4812 | XXX-XX-2be3 | ***-**-4812 | XXX-XX-d816 |
| dept | Engineering | Engineering | Engineering | Engineering |
| salary | $95,000 | [SCRUBBED:6842] | $95,*** | $95,000 |
| notes | Top performer... | 🗑 Deleted | Top ********** | Top performer... |

---

## Supported Formats

| Format | Extensions | Notes |
|--------|-----------|-------|
| CSV | `.csv` | Auto-detects encoding and dialect |
| SQL Dump | `.sql` | INSERT INTO ... VALUES statements |
| JSON | `.json` | Array of objects |
| PDF | `.pdf` | Text + scanned (PyMuPDF) |
| Word | `.docx` | Tables included |
| Excel | `.xlsx`, `.xls` | All sheets |
| Plain Text | `.txt`, `.md`, `.xml`, `.html`, `.log` | UTF-8/GBK/Latin-1 |

---

## PII Types Detected

### Regex Pass (50+ patterns, instant)
Emails, Phones (US/UK/EU/China), Credit Cards (Visa/MC/Amex/Discover), SSN, National Insurance, China ID, IBAN, SWIFT/BIC, IPv4/IPv6, API Keys, Tokens, Passwords, US ZIP, UK Postcode

### LLM Pass (contextual, requires Ollama for source install)
Person names, Physical addresses, Medical conditions, Salary figures, Family member names, License plates, VIN numbers, Internal URLs

### Column-Name Auto-Detection (35 patterns)
full_name, first_name, last_name, email, phone, mobile, ssn, passport, credit_card, salary, income, address, zip_code, dob, date_of_birth, ip_address, notes, comments, medical_history, bank_account, iban, swift, routing_number, driver_license, and more.

---

## Troubleshooting

### "Ollama not running" (source install only)
```bash
ollama serve
ollama pull qwen3.5:9b  # or your preferred model
```

### "License activation failed"
- Verify your key at https://getdatacleaner.com/verify
- Contact contact@getdatacleaner.com

### "File not found" on scrub-dump
- Use absolute paths: `dc scrub-dump C:/data/export.csv --level external`
- Check file permissions

### Recovery vault not found
- Recovery only works for admin mode (`--level admin --password KEY`)
- The `.vault` file must be in the same directory as the scrubbed CSV
- External and Internal modes use SHA-256 — irreversible by design

---

## Privacy & Security

- ✅ All processing happens on your machine
- ✅ Zero telemetry or analytics
- ✅ No network calls (even license validation is offline)
- ✅ Audit logs never contain actual PII values
- ✅ You remain the sole data controller (GDPR compliant)

---

## Need Help?

- 📧 Email: contact@getdatacleaner.com
- 🌐 Website: https://getdatacleaner.com
- 📖 Full docs: https://getdatacleaner.com/docs
- 🐛 Report issues: https://github.com/jennifer2026-sz/datacleaner-app/issues

---

**DataCleaner — Scrubbed Data That Still Works.**
