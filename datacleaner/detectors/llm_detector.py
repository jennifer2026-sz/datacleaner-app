"""LLM-based contextual PII detector — powered by local Ollama model."""

import json
import ollama
from datacleaner.config import load_config


PII_DETECTION_SYSTEM_PROMPT = """You are a precision PII (Personally Identifiable Information) detection system.

Your task: Analyze the given text and identify ALL instances of PII that regex-based detectors might miss. Focus on CONTEXTUAL PII — information that requires understanding meaning, not just pattern matching.

Categories to detect:
- PERSON_NAME: Full names, nicknames, aliases
- ADDRESS: Street addresses, PO boxes, physical locations
- ORGANIZATION: Company names when linked to individuals
- MEDICAL: Health conditions, treatments, diagnoses, medications
- FINANCIAL_CTX: Salary figures, account balances, transaction amounts with context
- AGE_DOB: Birth dates, ages (especially with names)
- FAMILY: Names of spouses, children, relatives
- VEHICLE: License plates, VIN numbers
- PERSONAL_ID: Passport numbers, driver's license numbers (even without standard format)
- CREDENTIALS: Usernames, passwords in plain text, internal URLs

IMPORTANT RULES:
1. Do NOT flag generic company names, product names, or public figures in non-private contexts.
2. Do NOT flag fictional/test data unless it's clearly meant to look real.
3. For each finding, provide the exact text, its position (character start/end), and a confidence score (0.0-1.0).
4. If you find nothing, return an empty list.
5. Focus on PRECISION over RECALL — false positives waste user time.

Return ONLY valid JSON with this exact structure:
{
  "findings": [
    {
      "category": "PERSON_NAME",
      "text": "John Smith",
      "start": 45,
      "end": 55,
      "confidence": 0.95,
      "reason": "Full name in patient context"
    }
  ]
}
"""


def detect_pii_llm(text: str, model: str = None) -> list[dict]:
    """Use local LLM to detect contextual PII in text.

    Args:
        text: The text chunk to analyze
        model: Ollama model name (defaults to config)

    Returns:
        List of findings dicts in the same format as regex detector
    """
    config = load_config()
    model = model or config["ollama"]["model"]
    timeout = config["ollama"]["timeout"]

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": PII_DETECTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this text for PII:\n\n```\n{text}\n```"},
            ],
            options={
                "temperature": 0.0,
                "num_predict": 2048,
            },
        )

        result_text = response["message"]["content"].strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```" in result_text:
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        data = json.loads(result_text)
        findings = data.get("findings", [])

        # Normalize format
        for f in findings:
            f["method"] = "llm"
            f["category"] = f.get("category", "UNKNOWN")
            f["type"] = f.get("category", "unknown").lower()
            f["match"] = f.get("text", "")
            # Ensure numeric positions
            f["start"] = int(f.get("start", 0))
            f["end"] = int(f.get("end", 0))

        # Filter low-confidence results
        threshold = config["scanning"]["confidence_threshold"]
        findings = [f for f in findings if f.get("confidence", 0) >= threshold]

        return findings

    except json.JSONDecodeError:
        # LLM returned malformed JSON — treat as no findings to avoid false positives
        return []
    except Exception as e:
        # Connection error, timeout, etc.
        error_msg = str(e)
        if "connection refused" in error_msg.lower():
            raise ConnectionError(
                "Cannot connect to Ollama. Is 'ollama serve' running?\n"
                f"Trying: {config['ollama']['host']}"
            )
        raise
