# DataCleaner PII Scrubber

A local, offline tool for deterministic pseudonymization of PII in CSV/Excel files.
Same input → same output across all tables. JOINs survive. No cloud. No telemetry.

---

## Installation

1. Install Python 3.10+ from [python.org](https://www.python.org/)
2. Open CMD (Windows) or Terminal (macOS/Linux) and run:

```bash
pip install datacleaner-pii-scrubber
```

3. Install GUI dependencies (for the desktop app):

```bash
pip install customtkinter
```

---

## How to Use (GUI)

1. Open CMD/Terminal and launch the GUI:

```bash
dc gui
```

2. In the GUI window:

| Step | Action |
|------|--------|
| Step 1 | Select a redaction level (see table below) |
| Step 2 | Click **Browse** to choose your CSV file |
| Step 3 | Click **Start Redaction** — the output `.xlsx` file is saved in the same folder |

---

## How to Use (Command Line)

```bash
# External — deterministic pseudonymization (SHA-256)
dc scrub-dump employees.csv --level external

# Internal — partial masking, business-readable
dc scrub-dump employees.csv --level internal

# Admin — AES-encrypted, recoverable with password
dc scrub-dump employees.csv --level admin --password "your-password"
```

All three levels output a formatted `.xlsx` file with professional styling.

---

## Redaction Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| **External** | Deterministic SHA-256 pseudonymization — same input always produces the same output, preserving cross-table JOINs | Sharing with external auditors/partners |
| **Internal** | Partial masking (e.g., given names visible, surname hidden) | Internal team use, business workflows |
| **Admin** | AES-256 encrypted tokenization, recoverable with password | Full compliance, internal audit trail |

### Same record, three views:

| Column | Original | External | Internal | Admin |
|--------|----------|----------|----------|-------|
| email | sarah@acme.com | `anon_d9ca@scrubbed.local` | `sar***@acmecorp.com` | `AES_f7a1@masked.local` |
| phone | +1-415-555-0134 | `+1-555-34b8` | `+1-***-***` | `AES_b23c` |
| ssn | 529-37-4812 | `XXX-XX-2be3` | `***-**-4812` | `AES_8d16` |
| salary | $95,000 | `[SCRUBBED]` | `$95,***` | `$95,000` |

---

## Recovery (Admin Level Only)

> Only Admin-level scrubbed files can be recovered. External and Internal use
> irreversible hashing — recovery is not possible by design.

1. Make sure the `.vault` file is in the same folder as your scrubbed `.xlsx` file
   (the vault is auto-generated during Admin-level scrubbing)
2. Run the recovery command:

```bash
dc recover your_file_admin.xlsx --password "your-password"
```

3. The original data is restored to a new `.csv` file

```bash
dc recover your_file_admin.xlsx --password "your-password" -o restored.csv
```

### Wrong password?

If you enter the wrong password, you will see:
> Error: Wrong password — cannot decrypt the recovery vault.

**Passwords cannot be recovered.** Keep the `.vault` file and your password safe.

---

## Features

- **100% Local** — All processing on your machine. No cloud calls, no telemetry.
- **Deterministic Hashing** — Same input → same output across tables, preserving
  SQL JOINs with no mapping table
- **Three Masking Levels** — External (irreversible), Internal (partial),
  Admin (AES-256 recoverable)
- **Professional XLSX Output** — Formatted with styled headers, auto-fit columns
- **50+ PII Patterns** — Emails, phones, SSN, credit cards, IBAN, IPs, and more
- **Audit Trails** — GDPR/HIPAA/CCPA compliant logs (never store actual PII values)

---

## PII Types Detected

**Regex (instant):** Emails, Phones (US/UK/EU/CN), Credit Cards (Visa/MC/Amex),
SSN, National Insurance, China ID, IBAN, SWIFT, IPv4/IPv6, API Keys, ZIP codes

**Column-name auto-detection:** full_name, first_name, email, phone, ssn,
credit_card, passport, salary, address, ip_address, dob, notes, comments,
medical_history, bank_account, and more

---

## All Commands

| Command | Description |
|---------|-------------|
| `dc gui` | Launch the graphical desktop app |
| `dc scan <path>` | Scan files/directories for PII |
| `dc scrub-dump <file>` | Scrub PII from CSV/SQL/JSON dumps |
| `dc recover <file>` | Recover Admin-level tokenized data |
| `dc audit` | View audit logs |
| `dc demo` | Run a 60-second demonstration |

### Common Options

| Option | Description |
|--------|-------------|
| `--level external\|internal\|admin` | Masking preset |
| `--password/-p <key>` | Admin-mode master password |
| `--output/-o <path>` | Output file path |
| `--json` | Output results as JSON |

---

## Important: Pseudonymization ≠ True Anonymization

DataCleaner performs **deterministic pseudonymization**, not true anonymization.
This distinction matters for compliance:

- **Pseudonymization** (what we do): The same real value always maps to the same
  pseudonym. This preserves SQL JOINs and cross-table queries, but the data is
  still considered personal data under GDPR (Article 4(5)).
- **True anonymization**: Data can never be re-identified. No JOINs survive.

**Before using DataCleaner in production, consult your compliance auditor.**
Different regulations have different standards:

| Regulation | Pseudonymization Status |
|-----------|------------------------|
| **GDPR** | Accepted with technical + organizational safeguards. Reduces breach notification obligations. |
| **HIPAA** | Expert Determination or Safe Harbor (18 identifiers) required for "de-identification." SHA-256 hashing alone does NOT satisfy Safe Harbor. |
| **CCPA** | Pseudonymized data is acceptable for de-identification purposes when re-identification risk is low. |

**Need HIPAA Safe Harbor compliance?** Contact us — we have a Safe Harbor mode
that removes all 18 identifiers. Available for Team tier customers.

---

## Notes

- All files are processed locally — no data is uploaded
- The `.vault` file is required for Admin-level recovery — **do not delete it**
- Passwords for Admin mode cannot be recovered — keep them safe
- External and Internal levels use irreversible SHA-256 hashing — data cannot
  be restored from these outputs

---

## Links

| Resource | URL |
|----------|-----|
| Website | https://getdatacleaner.com |
| GitHub | https://github.com/jennifer2026-sz/datacleaner-app |
| Buy Pro ($149) | https://galaxycontent.gumroad.com/l/qhfjnh |
| Buy Team ($399) | https://galaxycontent.gumroad.com/l/ijekp |
| Become an Affiliate | https://galaxycontent.gumroad.com/affiliates |

---

**Made by Jeam | Scrubbed Data That Still Works**
