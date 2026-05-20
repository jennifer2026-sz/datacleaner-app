"""DataCleaner Recovery Command — restore tokenized data.

Usage:
    dc recover <scrubbed_file> --password <your-password>
    dc recover <scrubbed_file> --password <your-password> -o restored.csv
"""

import csv
import sys
from pathlib import Path
from datacleaner.masking import TokenVault


def recover_scrambled(
    scrubbed_path: str | Path,
    password: str,
    output_path: str | Path | None = None,
) -> dict:
    """Recover original data from a tokenized (admin mode) scrubbed file.

    Requires the .vault file generated during admin-mode scrubbing.
    """
    scrubbed_path = Path(scrubbed_path)
    vault_path = Path(str(scrubbed_path) + ".vault")

    if not vault_path.exists():
        raise FileNotFoundError(
            f"Vault file not found: {vault_path}\n"
            "Recovery requires the .vault file generated during admin-mode scrubbing.\n"
            "If you used external or internal mode, recovery is not possible (SHA-256 irreversible)."
        )

    if output_path is None:
        output_path = scrubbed_path.parent / f"{scrubbed_path.stem}_recovered{scrubbed_path.suffix}"
    output_path = Path(output_path)

    # Load vault
    print(f"🔑 Loading recovery vault: {vault_path}")
    vault = TokenVault.load(password, vault_path)
    print(f"   {len(vault._mapping)} tokens loaded")

    # Read scrubbed file and recover
    with open(scrubbed_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    recovered_count = 0
    for row in rows:
        for header in headers:
            value = row[header]
            if value:
                original = vault.recover(value)
                if original:
                    row[header] = original
                    recovered_count += 1

    # Write recovered output
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers or [])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Recovered {recovered_count} values")
    print(f"   Output: {output_path}")

    return {
        "total_rows": len(rows),
        "recovered_cells": recovered_count,
        "output_path": str(output_path),
    }


# CLI entry point
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="DataCleaner Recovery — restore original data from admin-mode scrubbed files"
    )
    parser.add_argument("scrubbed_file", help="Path to scrubbed CSV file")
    parser.add_argument("--password", "-p", required=True, help="Master password used during admin-mode scrubbing")
    parser.add_argument("--output", "-o", help="Output path (default: <scrubbed>_recovered.csv)")

    args = parser.parse_args()

    try:
        recover_scrambled(args.scrubbed_file, args.password, args.output)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        # cryptography raises InvalidTag (subclass of ValueError) on wrong password
        msg = str(e)
        if "InvalidTag" in msg or "invalid" in msg.lower() or "bad decrypt" in msg.lower():
            print("Error: Wrong password — cannot decrypt the recovery vault.", file=sys.stderr)
            print("Make sure you are using the same password that was set during admin-mode scrubbing.", file=sys.stderr)
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
