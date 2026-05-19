"""Tests for partial masking feature."""

from datacleaner.redactor import redact_text, _partial_mask


class TestPartialMask:
    """Partial masking — preserve edges for analytics."""

    def test_email_partial_mask(self):
        """Email: preserve first+last char of local part, keep domain."""
        result = _partial_mask("john.smith@example.com", "email")
        assert "@example.com" in result
        assert result.startswith("j")
        assert result.endswith("@example.com")

    def test_email_short_local(self):
        """Short email local parts still partially masked."""
        result = _partial_mask("ab@test.com", "email")
        assert result.endswith("@test.com")

    def test_phone_us_partial_mask(self):
        """Phone: keep area code and last 3 digits."""
        result = _partial_mask("555-123-4567", "phone_us")
        assert result.startswith("555")
        assert "567" in result
        assert "***" in result

    def test_ssn_partial_mask(self):
        """SSN: only last 4 visible."""
        result = _partial_mask("123-45-6789", "ssn")
        assert result.endswith("6789")
        assert result.count("*") >= 5

    def test_credit_card_partial_mask(self):
        """Credit card: only last 4 visible."""
        result = _partial_mask("4111-1111-1111-1111", "credit_card")
        assert result.endswith("1111")
        assert "****" in result

    def test_name_partial_mask(self):
        """Name: initials visible."""
        result = _partial_mask("John Smith", "name")
        assert result.startswith("J")
        assert "S" in result

    def test_generic_partial_mask(self):
        """Generic: first and last char."""
        result = _partial_mask("abcdef", "generic")
        assert result.startswith("a")
        assert result.endswith("f")
        assert len(result) == 6

    def test_short_value(self):
        """Very short values fully masked."""
        result = _partial_mask("ab", "generic")
        assert result == "**"


class TestRedactTextPartial:
    """Integration: redact_text with partial style."""

    def test_partial_style_integration(self):
        """partial style should work through redact_text."""
        text = "Contact John at john@example.com or 555-123-4567"
        findings = [
            {"start": 8, "end": 12, "type": "name", "category": "person"},
            {"start": 17, "end": 35, "type": "email", "category": "contact"},
            {"start": 39, "end": 51, "type": "phone_us", "category": "contact"},
        ]
        result = redact_text(text, findings, style="partial")
        # John → J***
        assert "J" in result
        assert "***" in result
        # Email preserves domain
        assert "@example.com" in result
        # Phone preserves area code and last digits
        assert "555" in result
        assert "567" in result

    def test_partial_block_comparison(self):
        """partial should preserve more info than block."""
        text = "Email me at alice@company.com"
        findings = [{"start": 13, "end": 31, "type": "email", "category": "contact"}]

        blocked = redact_text(text, findings, style="block")
        partial = redact_text(text, findings, style="partial")

        assert "[REDACTED]" in blocked
        assert "@company.com" in partial
        assert "[REDACTED]" not in partial
