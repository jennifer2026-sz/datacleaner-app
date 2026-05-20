# DataCleaner — AI Development Workflow & Project Playbook

> **Purpose:** This document captures the complete development workflow, architecture decisions,
> and operational procedures for the DataCleaner project. It is designed to be read by
> another AI agent (or human developer) to understand the project at a glance and continue
> work without losing context.
>
> **Last Updated:** 2026-05-21
> **Project Owner:** Jeam (星辰), Shenzhen-based solo founder
> **GitHub:** jennifer2026-sz/datacleaner-app
> **Domain:** getdatacleaner.com
> **Distribution:** Gumroad (galaxycontent.gumroad.com)

---

## 1. Product Overview

DataCleaner is a **local-first CLI tool** for scrubbing Personally Identifiable Information (PII)
from database dumps, CSVs, and documents. The core differentiator is **deterministic hashing**
— same input always produces same output, preserving database JOIN integrity after anonymization.

**Pricing:** Pro $149 / Team $399 (one-time, perpetual license + optional annual update fee)

**Target Audience:** Engineering teams, compliance officers, data analysts, CTOs needing
GDPR/HIPAA/CCPA-compliant data sharing without breaking referential integrity.

---

## 2. Technical Architecture

### Core Modules

```
datacleaner/
├── masking.py          # L0-L4 tiered masking engine (the main feature)
├── recover.py          # AES-256-GCM recovery for admin mode
├── license.py          # Offline license key validation (SHA-256 checksum)
├── revocation.py       # Offline key revocation blacklist
├── revoked_keys.json   # Revoked key hashes (shipped with each release)
├── generate_licenses.py # CLI tool to generate license key CSVs
├── cli.py              # Click-based CLI (dc scan, dc scrub-dump, dc recover, dc audit)
├── scanner.py          # File scanner (regex + LLM)
├── redactor.py         # PII redaction engine
├── config.py           # User config management
├── commands/
│   └── scrub_dump.py   # Database dump scrubbing (CSV/SQL/JSON)
├── detectors/          # Regex patterns + LLM detector
├── processors/         # Format-specific processors (CSV/PDF/DOCX/TEXT)
└── utils/              # Streaming readers, converters, file utils
```

### Tiered Masking Engine (L0-L4)

| Level | Name | Behavior | Recoverable | Use Case |
|-------|------|----------|-------------|----------|
| L0 | Preserve | Keep original value | — | Non-PII columns |
| L1 | Partial Mask | Show edges, mask middle | No | Internal team sharing |
| L2 | Tokenize | AES-256-GCM encrypted tokens | ✅ With password | CEO/Admin access |
| L3 | Full Scrub | SHA-256 irreversible | No | Public release, compliance |
| L4 | Delete | Remove column entirely | No | Sensitive free-text fields |

Three preset modes:
- `--level external` = L3 + L4 (public datasets, auditors)
- `--level internal` = L1 (internal teams, support)
- `--level admin --password KEY` = L2 + L0 (recoverable, CEO)

### License Key System

- **Format:** `DCP-{base64_payload}:{sha256_checksum}` (Pro) / `DCT-...` (Team)
- **Validation:** 100% offline — Ed25519 signatures planned, currently SHA-256 checksum
- **Delivery:** Gumroad manual email (free tier doesn't support auto-delivery)
- **Revocation:** Offline blacklist (`revoked_keys.json`) — stores SHA-256 of key payload, NOT full keys

### Security Design

- **Zero cloud calls** — all processing is local
- **No telemetry** — no analytics, no phone-home
- **Offline license validation** — works without internet
- **Offline key revocation** — blacklist shipped with each release
- **Audit logs** — record what was scrubbed but never store actual PII values

---

## 3. Development Workflow

### Git Conventions

```
Commit types: feat: / fix: / refactor: / docs: / chore: / security:

Example:
  feat: tiered PII masking engine (L0-L4) with AES-256 recovery
  fix: SQL/JSON path now uses tiered masking engine
  security: remove vault & scrubbed outputs from git, harden .gitignore
```

### Pre-Push Security Checklist (MANDATORY)

Before every `git push`, the AI MUST run this checklist and report results:

1. **Sensitive file scan:** `git diff --cached --name-only` — check for `.vault`, `.key`, `.pem`, `.env`, `credentials.json`, `*_license_keys.csv`, `key_tracker.csv`
2. **Gitignore verification:** `git check-ignore` on all sensitive file patterns
3. **Chinese content scan:** All customer-facing files (docs/*.html, README.md, blog) must be English-only
4. **Tracked files audit:** `git ls-files` must NOT include: Jeam任务清单.md, 00_项目总控.md, any vault/credential files
5. **Report:** "已检查，无敏感数据，可以安全推送"

### Testing

```bash
# Run full test suite (from project root)
cd "/mnt/g/DeepSeek-Prodects/DataCleaner-PII脱敏工具"
python -m pytest tests/ -q

# Target: 174 tests, all must pass before any push
```

### Git Push (WSL-specific)

The WSL environment cannot execute Windows git.exe directly.
Push must be done from Windows PowerShell by the user:
```powershell
cd G:\DeepSeek-Prodects\DataCleaner-PII脱敏工具
git push
```

### Code Review Process

After writing code, the AI must self-review:
1. Line-by-line review of all changed files
2. Run exhaustive edge-case tests (not just unit tests)
3. Verify no regression in existing tests
4. Check for hardcoded secrets, credential leaks, Chinese in customer-facing files

---

## 4. Project File Structure

```
G:\DeepSeek-Prodects\DataCleaner-PII脱敏工具\
├── 00_项目总控.md              # Jeam's project master doc (NOT in git)
├── Jeam任务清单.md             # Jeam's personal task list (NOT in git)
├── .gitignore                  # Security rules (vault/keys/credentials blocked)
├── README.md                   # GitHub README (English, customer-facing)
├── LICENSE / EULA.md / PRIVACY.md
├── setup.py / pyproject.toml
├── datacleaner/                # Source code (25 .py files)
├── tests/                      # Pytest suite (174 tests)
├── docs/                       # Website (index, blog, purchase, privacy, terms, eula, dmca, sitemap)
└── 02_营销素材/                # Marketing materials (mixed git/private)
    ├── gumroad-listing-en.md   # Gumroad product page copy (in git)
    ├── install-guide-en.md     # Customer installation guide (in git)
    ├── email-templates-en.md   # Customer email templates (in git)
    ├── key-management-sop.md   # Jeam's key management SOP (in git)
    ├── screenshots/            # 5 product screenshots + thumbnail (in git)
    ├── 脱敏演示/               # Demo data & HTML report (in git, except .vault files)
    │   ├── employee_database_original.csv  # Synthetic demo data
    │   └── pii-masking-demo-report.html    # English demo report
    ├── pro_license_keys.csv    # Pro keys (NOT in git — .gitignore)
    ├── team_license_keys.csv   # Team keys (NOT in git — .gitignore)
    ├── key_tracker.csv         # Key usage tracker (NOT in git — .gitignore)
    ├── datacleaner-v0.2.0.zip  # Customer delivery package (NOT in git)
    ├── 定价调研报告_20260520.docx  # Internal pricing research (NOT in git)
    └── 美国法律合规报告_20260520.docx # Internal legal report (NOT in git)
```

### Files NEVER to commit (enforced by .gitignore)

- `*.vault`, `*.key`, `*.pem`, `*.pfx` — encryption material
- `*_scrubbed.csv`, `*_recovered.csv`, `*_admin.csv` — scrub output
- `.env`, `credentials.json`, `auth.json` — credentials
- `*_license_keys.csv`, `key_tracker.csv` — license keys
- `datacleaner-release-v*/` — build artifacts
- `Jeam任务清单.md`, `00_项目总控.md` — Jeam's private docs
- `*.sql.gz`, `*.dump`, `*.bak` — database dumps

---

## 5. Gumroad Operations

### Product URLs

| Product | URL | Status |
|---------|-----|--------|
| Pro ($149) | https://galaxycontent.gumroad.com/l/qhfjnh | ✅ Live |
| Team ($399) | https://galaxycontent.gumroad.com/l/ijekp | ✅ Live |

### Daily Key Distribution Workflow

1. Log into Gumroad → check new orders
2. Match order tier (Pro/Team) → grab next unused key from CSV
3. Send email using template from `email-templates-en.md`
4. Record in `key_tracker.csv`: `key,tier,email,date,status,order_id`
5. Status: `active` (in use) / `refunded` (burned) / `revoked` (disabled)

### Refund & Key Revocation

1. Process refund in Gumroad
2. Mark key as `refunded` in key_tracker.csv
3. Tell Jeam to run revocation command:
   ```python
   from datacleaner.revocation import add_revoked_key
   add_revoked_key("DCP-xxxx:yyyy", "Refund order #GUM-123")
   ```
4. Next release includes updated `revoked_keys.json`
5. Refunded customer sees: "This license key has been revoked."

### Regenerating License Keys

```bash
python datacleaner/generate_licenses.py --tier pro --count 100 -o pro_keys_batch2.csv
python datacleaner/generate_licenses.py --tier team --count 50 -o team_keys_batch2.csv
```

---

## 6. Website (getdatacleaner.com)

Static HTML site, deployed via GitHub Pages + Cloudflare CDN.

**Files:** `docs/index.html`, `docs/blog.html`, `docs/purchase.html`,
`docs/privacy.html`, `docs/terms.html`, `docs/eula.html`, `docs/dmca.html`

**Blog posts (7 articles):** All in `docs/blog.html` as inline HTML articles.
Newest first. Each post has: date, category tag, title, body with code blocks.

**Purchase buttons:** All point directly to Gumroad product URLs (not `purchase.html`).
Pro: `qhfjnh` / Team: `ijekp`.

---

## 7. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Deterministic hashing (SHA-256) over random anonymization | JOINs must survive scrubbing |
| Offline license validation | DataCleaner runs on customer hardware, no cloud dependency |
| Offline key revocation (blacklist) | No server infrastructure needed; acceptable trade-off for $149 tool |
| 3 modes, not 5 separate commands | One command with `--level` is simpler UX |
| Perpetual license + optional annual update | No recurring server costs to justify subscription |
| Email-based key delivery (manual) | Gumroad free tier limitation; acceptable at low volume |

---

## 8. Growth Channels (Planned)

| Channel | Status | Priority |
|---------|--------|----------|
| GitHub Topics | ✅ Set | Done |
| Technical Blog (blog.html) | ✅ 7 posts | Ongoing (2/week) |
| Reddit (r/Python, r/gdpr, r/devops) | ⬜ Not started | High |
| Hacker News (Show HN) | ⬜ Not started | High |
| Product Hunt | ⬜ Not started | Medium |
| Gumroad Discover | ⬜ Need first sale | Auto |

---

## 9. Commands Reference (for AI Agents)

### Running the tool
```bash
cd "/mnt/g/DeepSeek-Prodects/DataCleaner-PII脱敏工具"
python -m datacleaner.cli scrub-dump <file> --level external
python -m datacleaner.cli recover <file> --password <pwd>
python -m datacleaner.cli license activate <key>
```

### Testing
```bash
python -m pytest tests/ -q          # Full suite
python -m pytest tests/test_scrub_dump.py -v  # Specific module
```

### License key generation
```bash
python datacleaner/generate_licenses.py --tier pro --count 100 -o output.csv
```

### Key revocation
```bash
python -c "from datacleaner.revocation import add_revoked_key; add_revoked_key('DCP-xxx:yyy', 'Refund order #123')"
```

### Building customer package
```bash
# Package contents:
#   datacleaner/ (source)
#   README.md, INSTALL.md, LICENSE, pyproject.toml
#   demo/sample-employees.csv, demo/pii-masking-demo-report.html
# Zip and place in 02_营销素材/
```

---

## 10. Jeam's Role (Human Tasks)

| Task | Tool |
|------|------|
| Gumroad product management | Browser (指纹浏览器) |
| Key distribution | Email via Gumroad orders |
| Refund processing | Gumroad dashboard |
| Social media posting | Manual |
| Payment/legal/platform registration | Manual |

---

## 11. AI Agent Conventions

When working on this project, the AI agent should:

1. **Always run full test suite before pushing** (`python -m pytest tests/ -q`)
2. **Always run pre-push security checklist** (Section 3)
3. **Never commit sensitive files** (Section 4 — .gitignore list)
4. **All customer-facing content in English only**
5. **Internal Chinese docs (Jeam任务, 00_项目总控) stay local**
6. **Push is manual** — tell Jeam to run `git push` from Windows PowerShell
7. **After complex tasks, self-review code** (line-by-line, edge cases, regression)
8. **Save lessons learned** — update this document or create new docs as needed
9. **Gumroad URLs are live** — never change them without Jeam's confirmation
10. **DealFlow pattern:** AI does code/content; Jeam does payment/registration/legal

---

*This document is the canonical reference for the DataCleaner project.
When in doubt, read this first. When you learn something new, update this document.*
