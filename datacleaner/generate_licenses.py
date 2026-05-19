"""DataCleaner license key generator.

Generates license keys compatible with datacleaner/license.py validation.
Run offline. Output is a CSV ready for Gumroad license upload.

Usage:
    python generate_licenses.py --tier pro --count 100 --output pro_licenses.csv
    python generate_licenses.py --tier team --count 50  --output team_licenses.csv
    python generate_licenses.py --tier pro  --expires 2027-06-01 --count 20

Gumroad License CSV format:
    license_key
    DCP-xxxxx:yyyyyy
    DCP-zzzzz:wwwwww

The CSV is directly uploadable to Gumroad's license key system.
"""

import argparse
import base64
import csv
import hashlib
import json
import secrets
import sys
from datetime import datetime, timedelta


def _b64_encode(data: str) -> str:
    """URL-safe base64 encode (matches _b64_decode in license.py)."""
    encoded = base64.b64encode(data.encode()).decode()
    # Remove padding and make URL-safe
    return encoded.rstrip("=").replace("+", "-").replace("/", "_")


def _generate_key(tier: str, expires: str | None, serial: int) -> str:
    """Generate a single license key.

    Args:
        tier: 'pro' or 'team'
        expires: ISO date string (e.g., '2027-06-01') or None for no expiry
        serial: serial number for uniqueness
    """
    prefix = {"pro": "DCP-", "team": "DCT-"}[tier]

    payload = {
        "tier": tier,
        "serial": serial,
    }
    if expires:
        payload["expires"] = expires

    payload_str = json.dumps(payload, separators=(",", ":"))
    encoded = _b64_encode(payload_str)

    checksum = hashlib.sha256(
        f"datacleaner-salt-{encoded}".encode()
    ).hexdigest()[:8]

    return f"{prefix}{encoded}:{checksum}"


def generate_batch(
    tier: str,
    count: int,
    expires: str | None = None,
    output: str | None = None,
):
    """Generate a batch of licenses and write to CSV.

    Args:
        tier: 'pro' or 'team'
        count: number of licenses to generate
        expires: optional expiry date (YYYY-MM-DD)
        output: CSV file path (defaults to stdout)
    """
    keys = []
    for i in range(1, count + 1):
        key = _generate_key(tier, expires, i)
        keys.append(key)

    if output:
        with open(output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["license_key"])
            for key in keys:
                writer.writerow([key])
        print(f"✅ Generated {count} {tier} licenses → {output}")
    else:
        writer = csv.writer(sys.stdout)
        writer.writerow(["license_key"])
        for key in keys:
            writer.writerow([key])

    return keys


def verify_sample(keys: list[str], sample_size: int = 3):
    """Verify a few generated keys using the validation logic."""
    from datacleaner.license import validate_key

    import random
    samples = random.sample(keys, min(sample_size, len(keys)))
    print("\n🔍 Sample validation:")
    for key in samples:
        result = validate_key(key)
        status = "✅" if result["valid"] else "❌"
        print(f"  {status} {key[:30]}... → {result['tier']} | {result['message']}")


def main():
    parser = argparse.ArgumentParser(
        description="DataCleaner License Key Generator"
    )
    parser.add_argument(
        "--tier", required=True, choices=["pro", "team"],
        help="License tier"
    )
    parser.add_argument(
        "--count", type=int, default=100,
        help="Number of licenses to generate (default: 100)"
    )
    parser.add_argument(
        "--expires", type=str, default=None,
        help="Expiry date (YYYY-MM-DD). Omit for perpetual licenses."
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output CSV file path. Omit for stdout."
    )
    parser.add_argument(
        "--verify", action="store_true", default=True,
        help="Verify sample keys after generation (default: True)"
    )

    args = parser.parse_args()

    print(f"🔑 DataCleaner License Generator")
    print(f"   Tier: {args.tier}")
    print(f"   Count: {args.count}")
    print(f"   Expires: {args.expires or 'perpetual'}")
    print()

    keys = generate_batch(
        tier=args.tier,
        count=args.count,
        expires=args.expires,
        output=args.output,
    )

    if args.verify and args.output:
        verify_sample(keys)


if __name__ == "__main__":
    main()
