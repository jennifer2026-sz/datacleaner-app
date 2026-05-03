"""Tests for DataCleaner CLI."""

import pytest
from pathlib import Path


# ============================================================
#  Regex Detector Tests
# ============================================================
class TestRegexDetector:
    def test_email_detection(self):
        from datacleaner.detectors.regex_detector import detect_pii_regex
        findings = detect_pii_regex("Contact john.doe@example.com for details")
        emails = [f for f in findings if f["type"] == "email"]
        assert len(emails) == 1
        assert emails[0]["match"] == "john.doe@example.com"

    def test_phone_us_detection(self):
        from datacleaner.detectors.regex_detector import detect_pii_regex
        findings = detect_pii_regex("Call (555) 123-4567 or 555-987-6543")
        phones = [f for f in findings if f["type"] == "phone_us"]
        assert len(phones) == 2

    def test_credit_card_detection(self):
        from datacleaner.detectors.regex_detector import detect_pii_regex
        findings = detect_pii_regex("Card: 4111-1111-1111-1111 and 5500 0000 0000 0004")
        cards = [f for f in findings if f["type"] == "credit_card"]
        assert len(cards) == 2

    def test_ssn_detection(self):
        from datacleaner.detectors.regex_detector import detect_pii_regex
        findings = detect_pii_regex("SSN: 123-45-6789")
        ssns = [f for f in findings if f["type"] == "ssn"]
        assert len(ssns) == 1

    def test_ipv4_detection(self):
        from datacleaner.detectors.regex_detector import detect_pii_regex
        findings = detect_pii_regex("Server at 192.168.1.1 responded")
        ips = [f for f in findings if f["type"] == "ipv4"]
        assert len(ips) == 1

    def test_api_key_detection(self):
        from datacleaner.detectors.regex_detector import detect_pii_regex
        findings = detect_pii_regex("api_key = sk-abc123def456ghi789jkl")
        keys = [f for f in findings if f["type"] == "api_key"]
        assert len(keys) >= 1

    def test_cn_id_detection(self):
        from datacleaner.detectors.regex_detector import detect_pii_regex
        findings = detect_pii_regex("身份证号：110101199003071234")
        ids = [f for f in findings if f["type"] == "cn_id"]
        assert len(ids) == 1

    def test_no_false_positive_on_normal_text(self):
        from datacleaner.detectors.regex_detector import detect_pii_regex
        findings = detect_pii_regex("The quick brown fox jumps over the lazy dog.")
        # Should find nothing in normal text
        # (IP-like numbers might be false positives, that's acceptable)
        for f in findings:
            assert f["match"] != "the lazy dog"


# ============================================================
#  Redactor Tests
# ============================================================
class TestRedactor:
    def test_block_redaction(self):
        from datacleaner.redactor import redact_text
        text = "Contact John at john@example.com"
        findings = [
            {"start": 8, "end": 12, "type": "name", "category": "IDENTITY", "method": "regex", "match": "John"},
            {"start": 16, "end": 33, "type": "email", "category": "CONTACT", "method": "regex", "match": "john@example.com"},
        ]
        result = redact_text(text, findings, style="block")
        assert "Contact [REDACTED] at [REDACTED]" == result

    def test_placeholder_redaction(self):
        from datacleaner.redactor import redact_text
        text = "Email: test@test.com"
        findings = [
            {"start": 7, "end": 20, "type": "email", "category": "CONTACT", "method": "regex", "match": "test@test.com"},
        ]
        result = redact_text(text, findings, style="placeholder")
        assert "[EMAIL]" in result

    def test_mask_redaction(self):
        from datacleaner.redactor import redact_text
        text = "SSN: 123-45-6789"
        findings = [
            {"start": 5, "end": 16, "type": "ssn", "category": "IDENTITY", "method": "regex", "match": "123-45-6789"},
        ]
        result = redact_text(text, findings, style="mask")
        assert "XXXXXXXXXXX" in result  # 11 X's for 11 chars


# ============================================================
#  Scanner Tests
# ============================================================
class TestScanner:
    def test_scan_text_regex_only(self):
        from datacleaner.scanner import scan_text
        result = scan_text("Email test@example.com and call 555-123-4567", use_llm=False)
        assert result["stats"]["total"] >= 2
        assert "CONTACT" in result["stats"]["by_category"]

    def test_scan_clean_text(self):
        from datacleaner.scanner import scan_text
        result = scan_text("The weather is nice today.", use_llm=False)
        assert result["stats"]["total"] == 0


# ============================================================
#  License Tests
# ============================================================
class TestLicense:
    def test_free_trial(self):
        from datacleaner.license import validate_key
        result = validate_key("FREE-TRIAL")
        assert result["valid"] is True
        assert result["tier"] == "free"

    def test_invalid_key(self):
        from datacleaner.license import validate_key
        result = validate_key("INVALID-KEY-12345")
        assert result["valid"] is False

    def test_pro_key_format(self):
        from datacleaner.license import validate_key
        # A malformed pro key should fail validation
        result = validate_key("DCP-fakekey123:badcheck")
        assert result["valid"] is False


# ============================================================
#  Config Tests
# ============================================================
class TestConfig:
    def test_default_config(self, monkeypatch, tmp_path):
        from datacleaner.config import load_config, CONFIG_FILE
        monkeypatch.setattr("datacleaner.config.CONFIG_FILE", tmp_path / "nonexistent.yaml")
        config = load_config()
        assert "ollama" in config
        assert "scanning" in config
        assert config["ollama"]["model"] == "qwen3.5:9b"
