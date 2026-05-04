"""Tests for dc scrub-dump command."""
import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from datacleaner.commands.scrub_dump import (
    classify_columns,
    detect_pii_in_cell,
    _generate_fake_value,
    _parse_sql_insert,
    scrub_dump,
)


class TestDetectPiiInCell:
    def test_email_detection(self):
        findings = detect_pii_in_cell("john.smith@example.com")
        assert len(findings) > 0
        assert any(f["type"] == "email" for f in findings)

    def test_phone_us_detection(self):
        findings = detect_pii_in_cell("+1-555-123-4567")
        assert len(findings) > 0
        assert any("phone" in f["type"] for f in findings)

    def test_ssn_detection(self):
        findings = detect_pii_in_cell("123-45-6789")
        assert any(f["type"] == "ssn" for f in findings)

    def test_non_pii_returns_empty(self):
        findings = detect_pii_in_cell("Senior Engineer")
        assert findings == []

    def test_empty_cell(self):
        findings = detect_pii_in_cell("")
        assert findings == []

    def test_null_value(self):
        findings = detect_pii_in_cell("NULL")
        assert findings == []


class TestClassifyColumns:
    def test_detects_sensitive_columns(self):
        rows = [
            {"email": "a@b.com", "phone": "+1-555-111-2222", "dept": "Engineering"},
            {"email": "c@d.com", "phone": "+1-555-333-4444", "dept": "Sales"},
            {"email": "e@f.com", "phone": "+1-555-555-6666", "dept": "Marketing"},
        ]
        status = classify_columns(rows, ["email", "phone", "dept"])
        assert status["email"] is True
        assert status["phone"] is True
        assert status["dept"] is False

    def test_mixed_content_column(self):
        """Column with some PII but below threshold should be clean."""
        rows = []
        for i in range(50):
            rows.append({"col": "not pii text here"})
        for i in range(5):
            rows.append({"col": "a@b.com"})
        # 5/55 = 9% < 30% threshold
        status = classify_columns(rows, ["col"])
        assert status["col"] is False

    def test_empty_columns(self):
        rows = [{"empty": "", "full": "a@b.com"}]
        status = classify_columns(rows, ["empty", "full"])
        assert status["empty"] is False
        assert status["full"] is True


class TestGenerateFakeValue:
    def test_email_deterministic(self):
        v1 = _generate_fake_value("john@example.com", "email")
        v2 = _generate_fake_value("john@example.com", "email")
        assert v1 == v2  # same input = same output

    def test_email_format(self):
        v = _generate_fake_value("john@example.com", "email")
        assert v.endswith("@scrubbed.local")
        assert v.startswith("anon_")

    def test_phone_format(self):
        v = _generate_fake_value("+1-555-123-4567", "phone_us")
        assert v.startswith("+1-555-")

    def test_ssn_format(self):
        v = _generate_fake_value("123-45-6789", "ssn")
        assert v.startswith("XXX-XX-")

    def test_private_ip_preserved(self):
        v = _generate_fake_value("192.168.1.1", "ipv4")
        assert v == "192.168.1.1"

    def test_public_ip_anonymized(self):
        v = _generate_fake_value("8.8.8.8", "ipv4")
        assert v.startswith("10.")
        assert v != "8.8.8.8"


class TestParseSqlInsert:
    def test_simple_insert(self):
        parsed = _parse_sql_insert(
            "INSERT INTO users (name, email) VALUES ('John', 'john@test.com');"
        )
        assert parsed is not None
        assert parsed["table"] == "users"
        assert parsed["columns"] == ["name", "email"]
        assert parsed["values"] == [["'John'", "'john@test.com'"]]

    def test_multi_value_insert(self):
        parsed = _parse_sql_insert(
            "INSERT INTO t (a, b) VALUES ('x', 'y'), ('z', 'w');"
        )
        assert parsed is not None
        assert len(parsed["values"]) == 2

    def test_non_insert_returns_none(self):
        parsed = _parse_sql_insert("SELECT * FROM users;")
        assert parsed is None

    def test_backtick_columns(self):
        parsed = _parse_sql_insert(
            "INSERT INTO `users` (`first_name`, `last_name`) VALUES ('John', 'Doe');"
        )
        assert parsed is not None
        assert parsed["columns"] == ["first_name", "last_name"]


class TestScrubDumpIntegration:
    def test_csv_scrub_integration(self):
        """End-to-end test: create CSV with PII, scrub, verify output."""
        csv_content = (
            "name,email,phone,notes\n"
            "Alice,alice@test.com,+1-555-123-4567,Manager\n"
            "Bob,bob@test.com,+1-555-987-6543,Engineer\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            input_path = f.name

        output_path = str(Path(input_path).parent / "output_scrubbed.csv")

        try:
            stats = scrub_dump(
                input_path=input_path,
                output_path=output_path,
                style="placeholder",
                output_json=False,
            )

            # Verify stats
            assert stats["total_rows"] == 2
            assert "email" in stats["sensitive_columns"]
            assert "phone" in stats["sensitive_columns"]
            assert stats["total_cells_scrubbed"] == 4

            # Verify output file
            with open(output_path, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            # Emails should be scrubbed
            assert "@scrubbed.local" in rows[0]["email"]
            assert "@scrubbed.local" in rows[1]["email"]
            # Phone should be scrubbed (format-preserving)
            assert rows[0]["phone"].startswith("+1-555-")
            # Names should NOT be scrubbed (regex can't detect names)
            assert rows[0]["name"] == "Alice"
            assert rows[1]["name"] == "Bob"
            # Notes should NOT be scrubbed
            assert rows[0]["notes"] == "Manager"

        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)

    def test_json_scrub_integration(self):
        """End-to-end test with JSON input."""
        json_data = [
            {"user": "test1", "contact": "test1@acme.com"},
            {"user": "test2", "contact": "test2@acme.com"},
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(json_data, f)
            input_path = f.name

        output_path = str(Path(input_path).parent / "output_scrubbed.json")

        try:
            stats = scrub_dump(
                input_path=input_path,
                output_path=output_path,
                dump_format="json",
                output_json=False,
            )

            assert stats["total_rows"] == 2
            assert "contact" in stats["sensitive_columns"]

            with open(output_path, "r") as f:
                output_data = json.load(f)

            assert "@scrubbed.local" in output_data[0]["contact"]
            assert output_data[0]["user"] == "test1"

        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)

    def test_no_pii_dump(self):
        """Dump with no PII should produce clean copy."""
        csv_content = "dept,role,level\nEngineering,Developer,Senior\nSales,Manager,Lead\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            input_path = f.name

        output_path = str(Path(input_path).parent / "clean_output.csv")

        try:
            stats = scrub_dump(
                input_path=input_path,
                output_path=output_path,
            )

            assert stats["total_cells_scrubbed"] == 0
            assert stats["sensitive_columns"] == []

            # Output should exist
            assert Path(output_path).exists()

        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)
