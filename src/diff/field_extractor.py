"""
field_extractor.py — Extracts structured fields from trade confirmation documents.

Extracts four field categories:
  1. Economic Terms     — notional, rates, dates, payment frequency, day count
  2. Legal Clauses      — governing law, ISDA version, CSA, clearing
  3. Counterparty       — party A, party B, roles
  4. Trade Identity     — trade type, product, jurisdiction, version

Each field is tagged with a risk level (HIGH / MEDIUM / LOW) so the
diff engine can prioritise what needs human review.
"""

import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# ─── Risk Levels ──────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    HIGH   = "HIGH"    # Must be reviewed — economic impact or legal exposure
    MEDIUM = "MEDIUM"  # Should be reviewed — operational impact
    LOW    = "LOW"     # Informational — cosmetic or administrative


# ─── Field Model ──────────────────────────────────────────────────────────

@dataclass
class ExtractedField:
    """A single extracted field from a trade confirmation."""
    name: str               # Human-readable label
    key: str                # Machine key (snake_case)
    value: str              # Extracted value (empty string if not found)
    category: str           # "economic" | "legal" | "counterparty" | "identity"
    risk_level: RiskLevel   # HIGH / MEDIUM / LOW
    found: bool = True      # False if field was not found in document

    def __repr__(self):
        return f"Field({self.key}={self.value!r}, risk={self.risk_level})"


@dataclass
class ExtractedDocument:
    """All fields extracted from a single document."""
    filename: str
    fields: list[ExtractedField] = field(default_factory=list)

    def get(self, key: str) -> Optional[ExtractedField]:
        return next((f for f in self.fields if f.key == key), None)

    def by_category(self, category: str) -> list[ExtractedField]:
        return [f for f in self.fields if f.category == category]

    def by_risk(self, risk: RiskLevel) -> list[ExtractedField]:
        return [f for f in self.fields if f.risk_level == risk]

    @property
    def as_dict(self) -> dict:
        return {f.key: f.value for f in self.fields}


# ─── Field Definitions ────────────────────────────────────────────────────

FIELD_DEFINITIONS = [
    # ── Economic Terms ────────────────────────────────────────────────
    {
        "name":       "Notional Amount",
        "key":        "notional_amount",
        "category":   "economic",
        "risk_level": RiskLevel.HIGH,
        "patterns":   [
            r"Notional Amount\s*:\s*([^\n]+)",
            r"Notional\s*:\s*([^\n]+)",
        ],
    },
    {
        "name":       "Fixed Rate",
        "key":        "fixed_rate",
        "category":   "economic",
        "risk_level": RiskLevel.HIGH,
        "patterns":   [r"Fixed Rate\s*:\s*([^\n]+)"],
    },
    {
        "name":       "Floating Rate",
        "key":        "floating_rate",
        "category":   "economic",
        "risk_level": RiskLevel.HIGH,
        "patterns":   [r"Floating Rate\s*:\s*([^\n]+)"],
    },
    {
        "name":       "Effective Date",
        "key":        "effective_date",
        "category":   "economic",
        "risk_level": RiskLevel.HIGH,
        "patterns":   [
            r"Effective Date\s*:\s*([^\n]+)",
            r"Start Date\s*:\s*([^\n]+)",
        ],
    },
    {
        "name":       "Maturity Date",
        "key":        "maturity_date",
        "category":   "economic",
        "risk_level": RiskLevel.HIGH,
        "patterns":   [r"Maturity Date\s*:\s*([^\n]+)"],
    },
    {
        "name":       "Payment Frequency",
        "key":        "payment_frequency",
        "category":   "economic",
        "risk_level": RiskLevel.MEDIUM,
        "patterns":   [r"Payment Frequency\s*:\s*([^\n]+)"],
    },
    {
        "name":       "Day Count Convention",
        "key":        "day_count",
        "category":   "economic",
        "risk_level": RiskLevel.MEDIUM,
        "patterns":   [r"Day Count\s*:\s*([^\n]+)"],
    },

    # ── Legal Clauses ─────────────────────────────────────────────────
    {
        "name":       "Governing Law",
        "key":        "governing_law",
        "category":   "legal",
        "risk_level": RiskLevel.HIGH,
        "patterns":   [r"Governing Law\s*:\s*([^\n]+)"],
    },
    {
        "name":       "ISDA Agreement",
        "key":        "isda_version",
        "category":   "legal",
        "risk_level": RiskLevel.HIGH,
        "patterns":   [r"ISDA Agreement\s*:\s*([^\n]+)"],
    },
    {
        "name":       "Trade Type",
        "key":        "trade_type",
        "category":   "legal",
        "risk_level": RiskLevel.HIGH,
        "patterns":   [r"Trade Type\s*:\s*([^\n]+)"],
    },

    # ── Counterparty Details ──────────────────────────────────────────
    {
        "name":       "Parties",
        "key":        "parties",
        "category":   "counterparty",
        "risk_level": RiskLevel.HIGH,
        "patterns":   [r"Parties\s*:\s*([^\n]+)"],
    },
    {
        "name":       "Counterparty",
        "key":        "counterparty",
        "category":   "counterparty",
        "risk_level": RiskLevel.HIGH,
        "patterns":   [r"Counterparty\s*:\s*([^\n]+)"],
    },
    {
        "name":       "Jurisdiction",
        "key":        "jurisdiction",
        "category":   "counterparty",
        "risk_level": RiskLevel.MEDIUM,
        "patterns":   [r"Jurisdiction\s*:\s*([^\n]+)"],
    },

    # ── Trade Identity ────────────────────────────────────────────────
    {
        "name":       "Product",
        "key":        "product",
        "category":   "identity",
        "risk_level": RiskLevel.MEDIUM,
        "patterns":   [r"Product\s*:\s*([^\n]+)"],
    },
    {
        "name":       "Version",
        "key":        "version",
        "category":   "identity",
        "risk_level": RiskLevel.LOW,
        "patterns":   [r"Version\s*:\s*([^\n]+)"],
    },
    {
        "name":       "Status",
        "key":        "status",
        "category":   "identity",
        "risk_level": RiskLevel.LOW,
        "patterns":   [r"Status\s*:\s*([^\n]+)"],
    },
    {
        "name":       "Date",
        "key":        "document_date",
        "category":   "identity",
        "risk_level": RiskLevel.LOW,
        "patterns":   [r"^Date\s*:\s*([^\n]+)"],
    },
]


# ─── Extractor ────────────────────────────────────────────────────────────

class FieldExtractor:
    """
    Extracts structured fields from trade confirmation document text.

    Usage:
        extractor = FieldExtractor()
        doc = extractor.extract_from_text("full doc text...", filename="IRS_Goldman.docx")
        print(doc.get("notional_amount").value)
    """

    def extract_from_text(self, text: str, filename: str = "") -> ExtractedDocument:
        """Extract all defined fields from raw document text."""
        extracted = ExtractedDocument(filename=filename)

        for defn in FIELD_DEFINITIONS:
            value = self._extract_field(text, defn["patterns"])
            extracted.fields.append(ExtractedField(
                name=defn["name"],
                key=defn["key"],
                value=value,
                category=defn["category"],
                risk_level=defn["risk_level"],
                found=bool(value),
            ))

        return extracted

    def extract_from_file(self, file_path: Path) -> ExtractedDocument:
        """Parse a .docx file and extract fields."""
        from src.document_parser import DocumentParser
        parser = DocumentParser()
        doc = parser.parse(file_path)
        return self.extract_from_text(doc.full_text, filename=file_path.name)

    def extract_from_parsed(self, parsed_doc) -> ExtractedDocument:
        """Extract from an already-parsed ParsedDocument."""
        return self.extract_from_text(parsed_doc.full_text, filename=parsed_doc.filename)

    def _extract_field(self, text: str, patterns: list[str]) -> str:
        """Try each pattern in order; return first match, stripped."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
        return ""


if __name__ == "__main__":
    from src.template_generator import generate_all_templates
    from src.document_parser import DocumentParser
    from src.config import TEMPLATES_DIR

    generate_all_templates()
    extractor = FieldExtractor()
    parser = DocumentParser()

    docs = parser.parse_directory(TEMPLATES_DIR)
    print(f"\n📋 Field Extraction Demo\n{'─'*50}")
    for doc in docs[:2]:
        extracted = extractor.extract_from_parsed(doc)
        print(f"\n  {extracted.filename}")
        for f in extracted.fields:
            if f.found:
                risk_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[f.risk_level]
                print(f"    {risk_icon} {f.name:<25} {f.value[:50]}")
