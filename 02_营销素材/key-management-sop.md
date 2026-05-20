# DataCleaner License Key Management — SOP
# ==========================================
# Jeam's daily operations guide for manual key distribution via Gumroad.

---

## Daily Workflow

### Step 1: Check New Orders
- Log into Gumroad → Sales tab
- Filter by: Today + Product = DataCleaner Pro / Team
- Note each order: product (Pro/Team), buyer email, order ID

### Step 2: Issue Key
1. Open the key CSV file for the matching tier:
   - Pro:  `02_营销素材/pro_license_keys.csv`
   - Team: `02_营销素材/team_license_keys.csv`
2. Find the next UNUSED key (cross-check with `key_tracker.csv`)
3. Copy the key, paste into email template, send
4. **IMMEDIATELY** mark it in `key_tracker.csv`:
   ```
   DCP-eyJ0a...,pro,john@example.com,2026-05-20,active,Order #ABC123
   ```

### Step 3: Record
Update `key_tracker.csv` right after sending each email.
Never batch-record — do it one by one to avoid mistakes.

---

## Key Tracker File

Create a file: `G:\DeepSeek-Prodects\DataCleaner-PII脱敏工具\02_营销素材\key_tracker.csv`

```
key,tier,email,date,status,order_id
DCP-examplekey1,pro,customer@email.com,2026-05-20,active,GUM-001
DCT-examplekey2,team,biz@company.com,2026-05-20,active,GUM-002
```

Status values:
- `active` — issued, in use
- `refunded` — order refunded, key burned
- `revoked` — key disabled (e.g., abuse)
- `reserved` — pre-assigned, not yet sent

---

## How to Avoid Mistakes

### DO
- ✓ Copy-paste keys — never type manually
- ✓ Record in tracker BEFORE sending next email
- ✓ Double-check tier matches: Pro key for Pro order, Team for Team
- ✓ Pro keys start with `DCP-`, Team keys start with `DCT-`
- ✓ If unsure, run: `python datacleaner/generate_licenses.py --tier pro --count 1` to see what real keys look like

### DON'T
- ✗ Never send the same key to two customers
- ✗ Never send a Pro key for a Team order (or vice versa)
- ✗ Never share the full key CSV with anyone
- ✗ Never commit key CSV or tracker CSV to GitHub (.gitignore protects them, but be careful)

---

## Refund Handling

Since validation is **offline** (no way to remotely revoke), here's the procedure:

1. Customer requests refund → you process in Gumroad
2. Mark key as `refunded` in key_tracker.csv
3. Add note: `refunded,order=GUM-XXX,date=2026-05-25`
4. **Do NOT reissue that key.** It stays burned.
5. Generate replacement keys if running low:
   ```
   python datacleaner/generate_licenses.py --tier pro --count 20 -o pro_keys_batch2.csv
   ```
6. The refunded customer still has the old key file — but they refunded,
   so they've agreed not to use it. For CLI tools, this is standard practice.
   No major vendor (Sublime Text, JetBrains, etc.) can remotely revoke offline keys either.

If refund rate exceeds 10%, regenerate all keys and notify active customers.

---

## When Keys Run Low

Check remaining count weekly. When < 20 keys left for either tier:

```
python datacleaner/generate_licenses.py --tier pro --count 100 -o pro_keys_batch2.csv
python datacleaner/generate_licenses.py --tier team --count 50 -o team_keys_batch2.csv
```

Append new keys to your tracker. Old CSV can be archived.

---

## Customer Support Issues

### "Invalid license key" error
1. Ask customer to re-type the key (no extra spaces, no line breaks)
2. Verify the key starts with `DCP-` (Pro) or `DCT-` (Team)
3. If still fails, generate a fresh key and re-send. Mark old one as `revoked`.

### "dc command not found"
Customer didn't install correctly. Send them to:
- The INSTALL.md guide included in the download package
- Or: `pip install datacleaner` (if they have Python)

### "License expired" error  
Should not happen — keys are perpetual. If it does, the key was corrupted.
Generate and send a new one.

### Lost key / re-installation
Customer can check their original Gumroad email for the key.
If lost, verify their order in Gumroad → issue same key again (it's in your tracker).

---

## Quick Reference Card

| Situation | Action |
|-----------|--------|
| New Pro order | Grab next unused DCP- key → email → mark active |
| New Team order | Grab next unused DCT- key → email → mark active |
| Refund | Mark key `refunded` in tracker → do NOT reuse |
| Key error (customer) | Verify format → resend or generate new → mark old revoked |
| Running low (<20 left) | Generate new batch |
| Lost key | Look up in tracker → resend same key |

---

## File Locations

| File | Path | Protected? |
|------|------|-----------|
| Pro key CSV | `02_营销素材/pro_license_keys.csv` | .gitignore ✓ |
| Team key CSV | `02_营销素材/team_license_keys.csv` | .gitignore ✓ |
| Key tracker | `02_营销素材/key_tracker.csv` (create this) | .gitignore ✓ |
| Key generator | `datacleaner/generate_licenses.py` | Source code |
