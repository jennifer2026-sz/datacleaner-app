"""Tests for datacleaner.utils.converters — format conversion utilities.

Covers: CSV ↔ JSON, CSV ↔ dict, JSON ↔ dict, YAML ↔ JSON, format detection,
type coercion, edge cases (empty input, malformed data, encoding variants).
"""

import io
import json
import os
import tempfile
from pathlib import Path

import pytest


# ============================================================
#  Test Fixtures
# ============================================================

@pytest.fixture
def sample_csv_path(tmp_path):
    """Create a sample CSV file for testing."""
    path = tmp_path / "sample.csv"
    path.write_text(
        "name,email,score\r\n"
        "Alice,alice@example.com,95\r\n"
        "Bob,bob@example.com,87\r\n"
        "Charlie,charlie@example.com,92\r\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def sample_json_path(tmp_path):
    """Create a sample JSON file (array of objects) for testing."""
    path = tmp_path / "sample.json"
    data = [
        {"name": "Alice", "email": "alice@example.com", "score": 95},
        {"name": "Bob", "email": "bob@example.com", "score": 87},
    ]
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


@pytest.fixture
def sample_yaml_path(tmp_path):
    """Create a sample YAML file for testing."""
    path = tmp_path / "sample.yaml"
    import yaml
    data = [
        {"name": "Alice", "email": "alice@example.com", "active": True},
        {"name": "Bob", "email": "bob@example.com", "active": False},
    ]
    path.write_text(yaml.dump(data), encoding="utf-8")
    return str(path)


@pytest.fixture
def sample_json_single_object_path(tmp_path):
    """Create a JSON file with a single object (not wrapped in array)."""
    path = tmp_path / "single.json"
    path.write_text('{"name": "Solo", "email": "solo@test.com"}', encoding="utf-8")
    return str(path)


# ============================================================
#  csv_to_dicts
# ============================================================

class TestCsvToDicts:
    """Tests for csv_to_dicts — CSV file → list of dicts."""

    def test_basic_parsing(self, sample_csv_path):
        from datacleaner.utils.converters import csv_to_dicts

        result = csv_to_dicts(sample_csv_path)
        assert len(result) == 3
        assert result[0] == {"name": "Alice", "email": "alice@example.com", "score": "95"}

    def test_with_stringio(self):
        from datacleaner.utils.converters import csv_to_dicts

        buf = io.StringIO("a,b\n1,2\n3,4\n")
        result = csv_to_dicts(buf)
        assert result == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]

    def test_skip_empty_rows(self, tmp_path):
        from datacleaner.utils.converters import csv_to_dicts

        path = tmp_path / "gaps.csv"
        path.write_text("col1,col2\n\n\nvalue1,value2\n\n\n", encoding="utf-8")
        result = csv_to_dicts(str(path))
        # Should skip the empty rows
        assert len(result) == 1
        assert result[0] == {"col1": "value1", "col2": "value2"}

    def test_encoding_kwarg(self, tmp_path):
        from datacleaner.utils.converters import csv_to_dicts

        path = tmp_path / "utf16.csv"
        path.write_text("a,b\nx,y\n", encoding="utf-16")
        result = csv_to_dicts(str(path), encoding="utf-16")
        assert result == [{"a": "x", "b": "y"}]

    def test_custom_delimiter(self, tmp_path):
        from datacleaner.utils.converters import csv_to_dicts

        path = tmp_path / "tsv.csv"
        path.write_text("name\tage\nAlice\t30\n", encoding="utf-8")
        result = csv_to_dicts(str(path), delimiter="\t")
        assert result == [{"name": "Alice", "age": "30"}]

    def test_file_not_found(self):
        from datacleaner.utils.converters import csv_to_dicts

        with pytest.raises(FileNotFoundError):
            csv_to_dicts("/nonexistent/path.csv")

    def test_invalid_source_type(self):
        from datacleaner.utils.converters import csv_to_dicts

        with pytest.raises(TypeError, match="source must be"):
            csv_to_dicts(123)  # type: ignore


# ============================================================
#  dicts_to_csv
# ============================================================

class TestDictsToCsv:
    """Tests for dicts_to_csv — list of dicts → CSV string."""

    def test_basic_serialization(self):
        from datacleaner.utils.converters import dicts_to_csv

        data = [
            {"name": "Alice", "score": 95},
            {"name": "Bob", "score": 87},
        ]
        result = dicts_to_csv(data)
        lines = result.strip().split("\r\n")
        assert lines[0] == "name,score"
        assert lines[1] == "Alice,95"
        assert lines[2] == "Bob,87"

    def test_no_header(self):
        from datacleaner.utils.converters import dicts_to_csv

        data = [{"x": "1"}, {"x": "2"}]
        result = dicts_to_csv(data, include_header=False)
        assert "1" in result
        assert "x" not in result  # No header row

    def test_custom_delimiter(self):
        from datacleaner.utils.converters import dicts_to_csv

        data = [{"a": "1", "b": "2"}]
        result = dicts_to_csv(data, delimiter="\t")
        assert "\t" in result

    def test_empty_data_raises(self):
        from datacleaner.utils.converters import dicts_to_csv

        with pytest.raises(ValueError, match="must not be empty"):
            dicts_to_csv([])

    def test_non_string_values_stringified(self):
        from datacleaner.utils.converters import dicts_to_csv

        data = [{"name": "Alice", "active": True, "count": 42, "ratio": 0.5}]
        result = dicts_to_csv(data)
        # All values should be stringified
        assert "True" in result
        assert "42" in result
        assert "0.5" in result

    def test_roundtrip(self, tmp_path):
        """dicts_to_csv → csv_to_dicts should be lossless for string data."""
        from datacleaner.utils.converters import dicts_to_csv, csv_to_dicts

        original = [
            {"name": "Alice", "email": "a@b.com"},
            {"name": "Bob", "email": "b@c.com"},
        ]
        csv_str = dicts_to_csv(original)

        path = tmp_path / "roundtrip.csv"
        path.write_text(csv_str, encoding="utf-8")
        result = csv_to_dicts(str(path))

        assert result == original


# ============================================================
#  csv_to_json / json_to_csv
# ============================================================

class TestCsvJsonConversion:
    """Tests for CSV ↔ JSON round-trip conversion."""

    def test_csv_to_json(self, sample_csv_path):
        from datacleaner.utils.converters import csv_to_json

        result = csv_to_json(sample_csv_path)
        parsed = json.loads(result)
        assert len(parsed) == 3
        assert parsed[0]["name"] == "Alice"

    def test_csv_to_json_compact(self, tmp_path):
        from datacleaner.utils.converters import csv_to_json

        path = tmp_path / "mini.csv"
        path.write_text("k,v\na,1\n", encoding="utf-8")
        result = csv_to_json(str(path), indent=0)
        # Compact JSON — no pretty-print newlines
        assert "\n" not in result.strip()

    def test_json_to_csv_from_file(self, sample_json_path):
        from datacleaner.utils.converters import json_to_csv

        result = json_to_csv(sample_json_path)
        assert "name,email,score" in result
        assert "Alice" in result

    def test_json_to_csv_from_list(self):
        from datacleaner.utils.converters import json_to_csv

        data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = json_to_csv(data)
        assert result.startswith("a,b")

    def test_roundtrip_csv_json_csv(self, sample_csv_path, tmp_path):
        from datacleaner.utils.converters import csv_to_json, json_to_csv
        from datacleaner.utils.converters import csv_to_dicts

        original = csv_to_dicts(sample_csv_path)
        json_str = csv_to_json(sample_csv_path)
        json_path = tmp_path / "intermediate.json"
        json_path.write_text(json_str, encoding="utf-8")
        result = json_to_csv(str(json_path))

        path = tmp_path / "final.csv"
        path.write_text(result, encoding="utf-8")
        final = csv_to_dicts(str(path))
        assert final == original


# ============================================================
#  json_to_dicts
# ============================================================

class TestJsonToDicts:
    """Tests for json_to_dicts — JSON file → list of dicts."""

    def test_array_of_objects(self, sample_json_path):
        from datacleaner.utils.converters import json_to_dicts

        result = json_to_dicts(sample_json_path)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"

    def test_single_object_wrapped(self, sample_json_single_object_path):
        from datacleaner.utils.converters import json_to_dicts

        result = json_to_dicts(sample_json_single_object_path)
        assert len(result) == 1
        assert result[0]["name"] == "Solo"

    def test_scalar_root_raises(self, tmp_path):
        from datacleaner.utils.converters import json_to_dicts

        path = tmp_path / "bad.json"
        path.write_text('"just a string"', encoding="utf-8")
        with pytest.raises(ValueError, match="JSON root must be"):
            json_to_dicts(str(path))

    def test_file_not_found(self):
        from datacleaner.utils.converters import json_to_dicts

        with pytest.raises(FileNotFoundError):
            json_to_dicts("/nonexistent.json")


# ============================================================
#  dicts_to_json
# ============================================================

class TestDictsToJson:
    """Tests for dicts_to_json — list of dicts → JSON string."""

    def test_basic_serialization(self):
        from datacleaner.utils.converters import dicts_to_json

        result = dicts_to_json([{"a": 1}])
        parsed = json.loads(result)
        assert parsed == [{"a": 1}]

    def test_compact_mode(self):
        from datacleaner.utils.converters import dicts_to_json

        result = dicts_to_json([{"a": 1, "b": 2}], indent=0)
        assert "\n" not in result

    def test_ensure_ascii(self):
        from datacleaner.utils.converters import dicts_to_json

        result = dicts_to_json([{"name": "Jürgen"}], ensure_ascii=True)
        assert "\\u00fc" in result

    def test_sort_keys(self):
        from datacleaner.utils.converters import dicts_to_json

        result = dicts_to_json([{"b": 2, "a": 1}], sort_keys=True)
        assert result.index('"a"') < result.index('"b"')


# ============================================================
#  YAML Conversions
# ============================================================

class TestYamlConversions:
    """Tests for YAML ↔ JSON / CSV conversions."""

    def test_yaml_to_dicts(self, sample_yaml_path):
        from datacleaner.utils.converters import yaml_to_dicts

        result = yaml_to_dicts(sample_yaml_path)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[0]["active"] is True

    def test_yaml_to_dicts_empty_file(self, tmp_path):
        from datacleaner.utils.converters import yaml_to_dicts

        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")
        result = yaml_to_dicts(str(path))
        assert result == []

    def test_yaml_to_json(self, sample_yaml_path):
        from datacleaner.utils.converters import yaml_to_json

        result = yaml_to_json(sample_yaml_path)
        parsed = json.loads(result)
        assert parsed[0]["name"] == "Alice"

    def test_csv_to_yaml(self, sample_csv_path):
        from datacleaner.utils.converters import csv_to_yaml

        result = csv_to_yaml(sample_csv_path)
        assert "name: Alice" in result
        assert "email:" in result

    def test_yaml_roundtrip(self, sample_yaml_path, tmp_path):
        """YAML → JSON → check data equivalence."""
        from datacleaner.utils.converters import yaml_to_dicts, csv_to_yaml
        from datacleaner.utils.converters import csv_to_dicts

        # Convert YAML → CSV path → validate
        yaml_data = yaml_to_dicts(sample_yaml_path)
        # Write as CSV, read back
        import csv
        csv_path = tmp_path / "from_yaml.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["name", "email", "active"])
            w.writeheader()
            w.writerows(yaml_data)

        result = csv_to_dicts(str(csv_path))
        assert result[0]["name"] == "Alice"


# ============================================================
#  detect_format
# ============================================================

class TestDetectFormat:
    """Tests for detect_format — extension-based format detection."""

    @pytest.mark.parametrize("filename,expected", [
        ("data.csv", "csv"),
        ("data.tsv", "tsv"),
        ("data.json", "json"),
        ("config.yaml", "yaml"),
        ("config.yml", "yaml"),
        ("report.xlsx", "excel"),
        ("data.parquet", "parquet"),
        ("log.xml", "xml"),
        ("notes.txt", "text"),
        ("README.md", "text"),
        ("debug.log", "text"),
    ])
    def test_known_formats(self, filename, expected):
        from datacleaner.utils.converters import detect_format

        assert detect_format(filename) == expected

    def test_unknown_format(self):
        from datacleaner.utils.converters import detect_format

        assert detect_format("image.png") is None
        assert detect_format("video.mp4") is None
        assert detect_format("noextension") is None

    def test_case_insensitive(self):
        from datacleaner.utils.converters import detect_format

        assert detect_format("DATA.CSV") == "csv"
        assert detect_format("Config.YAML") == "yaml"

    def test_with_path_object(self):
        from datacleaner.utils.converters import detect_format

        assert detect_format(Path("/some/path/data.json")) == "json"


# ============================================================
#  normalize_row
# ============================================================

class TestNormalizeRow:
    """Tests for normalize_row — row cleaning and type coercion."""

    def test_strip_whitespace(self):
        from datacleaner.utils.converters import normalize_row

        row = {" name ": "  Alice  ", "city": "Paris"}
        result = normalize_row(row)
        assert result[" name "] == "Alice"
        assert result["city"] == "Paris"

    def test_no_strip(self):
        from datacleaner.utils.converters import normalize_row

        row = {"code": "  001  "}
        result = normalize_row(row, strip=False)
        assert result["code"] == "  001  "

    def test_lowercase_keys(self):
        from datacleaner.utils.converters import normalize_row

        row = {"Name": "Alice", "EMAIL": "a@b.com"}
        result = normalize_row(row, lowercase_keys=True)
        assert "name" in result
        assert "email" in result
        assert result["email"] == "a@b.com"

    def test_bool_coercion(self):
        from datacleaner.utils.converters import normalize_row

        row = {"active": "true", "deleted": "false"}
        result = normalize_row(row)
        assert result["active"] is True
        assert result["deleted"] is False

    def test_int_coercion(self):
        from datacleaner.utils.converters import normalize_row

        row = {"count": "42", "negative": "-7"}
        result = normalize_row(row)
        assert result["count"] == 42
        assert result["negative"] == -7

    def test_float_coercion(self):
        from datacleaner.utils.converters import normalize_row

        row = {"ratio": "0.75", "sci": "1.5e2"}
        result = normalize_row(row)
        assert result["ratio"] == 0.75
        assert result["sci"] == 150.0

    def test_null_coercion(self):
        from datacleaner.utils.converters import normalize_row

        for sentinel in ("", "null", "none", "nil", "na", "n/a", "N/A"):
            row = {"value": sentinel}
            result = normalize_row(row)
            assert result["value"] is None, f"'{sentinel}' should coerce to None"

    def test_non_string_values_passthrough(self):
        from datacleaner.utils.converters import normalize_row

        row = {"int_val": 42, "float_val": 3.14, "bool_val": True}
        result = normalize_row(row)
        assert result["int_val"] == 42
        assert result["float_val"] == 3.14
        assert result["bool_val"] is True

    def test_original_not_mutated(self):
        from datacleaner.utils.converters import normalize_row

        original = {" Name ": " Alice "}
        normalized = normalize_row(original)
        assert original[" Name "] == " Alice "  # Original unchanged
        assert normalized[" Name "] == "Alice"

    def test_empty_string_becomes_none(self):
        from datacleaner.utils.converters import normalize_row

        row = {"blank": ""}
        result = normalize_row(row)
        assert result["blank"] is None
