# SECURITY: File Classification Rules

> **This file is the source of truth. Every new file created in this project
> MUST be classified BEFORE it is written to disk. There is no undo on GitHub.**

---

## Classification Rule (Mandatory — Apply Before Creating ANY File)

| Category | Rule | Examples |
|----------|------|----------|
| **PUBLIC** | Customer-facing, demo data, open-source code | README.md, docs/*.html, *.py, employee_database_original.csv, screenshots/*.png |
| **INTERNAL** | Business ops, pricing, legal, Jeam's docs, AI workflows, keys, credentials | Jeam任务清单.md, *.docx, *SOP*, *.vault, *_license_keys.csv, key_tracker.csv |

### Decision Flow

```
Creating a new file? Ask:

1. Does it contain passwords, API keys, license keys, or tokens?
   → YES: INTERNAL — .gitignore it IMMEDIATELY

2. Does it describe Jeam's internal processes (pricing, legal, operations)?
   → YES: INTERNAL — .gitignore it IMMEDIATELY

3. Is it a build artifact or generated output (.zip, .egg-info, _scrubbed.csv)?
   → YES: INTERNAL — .gitignore it IMMEDIATELY

4. Is it a database dump, backup, or real PII data?
   → YES: INTERNAL — .gitignore it IMMEDIATELY

5. Everything else → PUBLIC — safe to commit
```

---

## File Patterns Reference

### NEVER Push (enforced by .gitignore)

```
# Encryption & keys
*.vault, *.key, *.pem, *.pfx, *.p12, *.jks, *.keystore

# Credentials
.env, .env.*, *.env, credentials.json, auth.json, *.token
secrets.yaml, secrets.yml

# License keys & tracking
*_license_keys.csv, key_tracker.csv

# Internal business docs
02_营销素材/*.docx, 02_营销素材/*.doc
02_营销素材/key-management-sop.md
02_营销素材/email-templates-en.md

# AI internal docs
.AI_*, _AI_*

# Jeam's private docs
Jeam任务清单.md, 00_项目总控.md

# Build artifacts
datacleaner-release-v*/, datacleaner-v*.zip
*.egg-info/, __pycache__/, *.pyc

# Database dumps
*.sql.gz, *.dump, *.bak

# Scrubbed outputs
*_scrubbed.csv, *_recovered.csv, *_external.csv, *_internal.csv, *_admin.csv
```

### ALWAYS Safe to Push

```
Source code:     datacleaner/*.py, tests/*.py
Docs/website:    docs/*.html, docs/*.xml, README.md, LICENSE, EULA.md, PRIVACY.md
Config:          setup.py, pyproject.toml, setup.cfg, .gitignore, SECURITY.md
Marketing:       gumroad-listing-en.md, install-guide-en.md
Screenshots:     02_营销素材/screenshots/*.png
Demo data:       02_营销素材/脱敏演示/employee_database_original.csv
Demo report:     02_营销素材/脱敏演示/pii-masking-demo-report.html
AI workflow:     .AI_WORKFLOW.md (dot-prefixed = local only)
```

---

## Pre-Push Checklist (Run Before EVERY Push)

```
[ ] git diff --cached --name-only — review every staged file
[ ] For each file: does it match ANY "NEVER Push" pattern?
[ ] git check-ignore on any suspicious file — must return the .gitignore rule
[ ] No Chinese in customer-facing files (docs/*.html, README.md)
[ ] Report: "已检查，无敏感数据，可以安全推送"
```

---

## Incident Log

| Date | Incident | Root Cause | Prevention |
|------|----------|------------|------------|
| 2026-05-21 | AI_WORKFLOW.md pushed | Not in .gitignore | Added .AI_* rule |
| 2026-05-21 | .docx reports pushed | git add -A without review | Added 02_营销素材/*.docx rule; mandatory pre-push review |
| 2026-05-21 | key-management-sop.md pushed | Not classified as internal at creation | Created this SECURITY.md; classification-before-creation rule |
| 2026-05-20 | .vault file pushed | No .gitignore rule for vault files | Added *.vault rule; comprehensive security audit |
