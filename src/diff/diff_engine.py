"""
diff_engine.py — Core difference highlighting engine.

Compares two trade confirmation documents and identifies discrepancies
across all critical fields. Each discrepancy is tagged with:
  - Risk severity (HIGH / MEDIUM / LOW)
  - Change type (CHANGED / MISSING / ADDED / NUMERIC_DRIFT)
  - Numeric analysis for economic fields (% change, absolute delta)
  - Semantic similarity score for clause text

Pipeline:
  template doc  ──┐
                  ├── DiffEngine.compare() ──> DiffReport
  incoming doc  ──┘
"""

import re
import math
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.diff.field_extractor import (
    FieldExtractor, ExtractedDocument, ExtractedField, RiskLevel
)


# ─── Change Types ─────────────────────────────────────────────────────────

class ChangeType(str, Enum):
    CHANGED       = "CHANGED"        # Value exists in both but differs
    MISSING       = "MISSING"        # Field present in template, absent in incoming
    ADDED         = "ADDED"          # Field present in incoming, absent in template
    NUMERIC_DRIFT = "NUMERIC_DRIFT"  # Numeric field changed (shows % delta)
    MATCH         = "MATCH"          # Fields are identical


# ─── Discrepancy Model ────────────────────────────────────────────────────

@dataclass
class Discrepancy:
    """A single detected difference between template and incoming document."""
    field_name:      str
    field_key:       str
    category:        str
    risk_level:      RiskLevel
    change_type:     ChangeType
    template_value:  str
    incoming_value:  str

    # Numeric analysis (for economic fields)
    numeric_delta:   Optional[float] = None   # Absolute difference
    numeric_pct:     Optional[float] = None   # % change

    # Semantic similarity (0–1, for text fields)
    similarity:      Optional[float] = None

    # Human-readable explanation
    explanation:     str = ""

    @property
    def is_critical(self) -> bool:
        return self.risk_level == RiskLevel.HIGH

    @property
    def risk_icon(self) -> str:
        return {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[self.risk_level]

    @property
    def change_icon(self) -> str:
        return {
            ChangeType.CHANGED:       "⚡",
            ChangeType.MISSING:       "❌",
            ChangeType.ADDED:         "➕",
            ChangeType.NUMERIC_DRIFT: "📊",
            ChangeType.MATCH:         "✅",
        }[self.change_type]

    def __repr__(self):
        return (f"Discrepancy({self.field_key}: "
                f"{self.template_value!r} → {self.incoming_value!r}, "
                f"risk={self.risk_level})")


@dataclass
class DiffReport:
    """Complete diff report comparing template vs incoming document."""
    template_filename: str
    incoming_filename: str
    discrepancies:     list[Discrepancy] = field(default_factory=list)
    matches:           list[Discrepancy] = field(default_factory=list)

    @property
    def high_risk(self) -> list[Discrepancy]:
        return [d for d in self.discrepancies if d.risk_level == RiskLevel.HIGH]

    @property
    def medium_risk(self) -> list[Discrepancy]:
        return [d for d in self.discrepancies if d.risk_level == RiskLevel.MEDIUM]

    @property
    def low_risk(self) -> list[Discrepancy]:
        return [d for d in self.discrepancies if d.risk_level == RiskLevel.LOW]

    @property
    def total_discrepancies(self) -> int:
        return len(self.discrepancies)

    @property
    def risk_score(self) -> float:
        """Composite risk score 0–100. Higher = more risky."""
        weights = {RiskLevel.HIGH: 10, RiskLevel.MEDIUM: 3, RiskLevel.LOW: 1}
        raw = sum(weights[d.risk_level] for d in self.discrepancies)
        return min(100.0, raw)

    @property
    def needs_review(self) -> bool:
        return len(self.high_risk) > 0

    def summary(self) -> str:
        return (
            f"DiffReport: {self.template_filename} vs {self.incoming_filename}\n"
            f"  Discrepancies: {self.total_discrepancies} "
            f"(🔴{len(self.high_risk)} HIGH, "
            f"🟡{len(self.medium_risk)} MEDIUM, "
            f"🟢{len(self.low_risk)} LOW)\n"
            f"  Matches: {len(self.matches)}\n"
            f"  Risk Score: {self.risk_score:.0f}/100\n"
            f"  Needs Review: {'YES' if self.needs_review else 'NO'}"
        )

    def to_dict(self) -> dict:
        return {
            "template_filename": self.template_filename,
            "incoming_filename": self.incoming_filename,
            "total_discrepancies": self.total_discrepancies,
            "high_risk_count":    len(self.high_risk),
            "medium_risk_count":  len(self.medium_risk),
            "low_risk_count":     len(self.low_risk),
            "risk_score":         self.risk_score,
            "needs_review":       self.needs_review,
            "discrepancies": [
                {
                    "field_name":     d.field_name,
                    "field_key":      d.field_key,
                    "category":       d.category,
                    "risk_level":     d.risk_level,
                    "change_type":    d.change_type,
                    "template_value": d.template_value,
                    "incoming_value": d.incoming_value,
                    "numeric_delta":  d.numeric_delta,
                    "numeric_pct":    d.numeric_pct,
                    "similarity":     d.similarity,
                    "explanation":    d.explanation,
                }
                for d in self.discrepancies
            ],
            "matches": [
                {"field_key": m.field_key, "value": m.template_value}
                for m in self.matches
            ],
        }


# ─── Diff Engine ──────────────────────────────────────────────────────────

class DiffEngine:
    """
    Compares two trade confirmation documents field by field.

    Usage:
        engine = DiffEngine()
        report = engine.compare(template_doc, incoming_doc)
        print(report.summary())
    """

    # Numeric tolerance: differences < this % are not flagged
    NUMERIC_TOLERANCE_PCT = 0.001   # 0.1%

    def compare(
        self,
        template: ExtractedDocument,
        incoming: ExtractedDocument,
    ) -> DiffReport:
        """
        Compare template vs incoming document.

        Args:
            template: Fields extracted from the reference template.
            incoming: Fields extracted from the new/incoming confirmation.

        Returns:
            DiffReport with all discrepancies tagged and scored.
        """
        report = DiffReport(
            template_filename=template.filename,
            incoming_filename=incoming.filename,
        )

        # Build lookup dict for incoming fields
        incoming_lookup = {f.key: f for f in incoming.fields}

        for tmpl_field in template.fields:
            inc_field = incoming_lookup.get(tmpl_field.key)

            if inc_field is None:
                # Field not defined in incoming at all
                if tmpl_field.found:
                    report.discrepancies.append(Discrepancy(
                        field_name=tmpl_field.name,
                        field_key=tmpl_field.key,
                        category=tmpl_field.category,
                        risk_level=tmpl_field.risk_level,
                        change_type=ChangeType.MISSING,
                        template_value=tmpl_field.value,
                        incoming_value="",
                        explanation=f"'{tmpl_field.name}' is present in template but missing in incoming document.",
                    ))
                continue

            # Both exist — compare values
            discrepancy = self._compare_fields(tmpl_field, inc_field)
            if discrepancy.change_type == ChangeType.MATCH:
                report.matches.append(discrepancy)
            else:
                report.discrepancies.append(discrepancy)

        # Check for fields in incoming that aren't in the template
        template_keys = {f.key for f in template.fields}
        for inc_field in incoming.fields:
            if inc_field.key not in template_keys and inc_field.found:
                report.discrepancies.append(Discrepancy(
                    field_name=inc_field.name,
                    field_key=inc_field.key,
                    category=inc_field.category,
                    risk_level=RiskLevel.LOW,
                    change_type=ChangeType.ADDED,
                    template_value="",
                    incoming_value=inc_field.value,
                    explanation=f"'{inc_field.name}' found in incoming document but not in template.",
                ))

        # Sort discrepancies: HIGH first, then MEDIUM, then LOW
        risk_order = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
        report.discrepancies.sort(key=lambda d: risk_order[d.risk_level])

        return report

    def compare_texts(
        self,
        template_text: str,
        incoming_text: str,
        template_name: str = "template",
        incoming_name: str = "incoming",
    ) -> DiffReport:
        """Convenience method: compare raw text strings directly."""
        extractor = FieldExtractor()
        tmpl_doc = extractor.extract_from_text(template_text, template_name)
        inc_doc  = extractor.extract_from_text(incoming_text, incoming_name)
        return self.compare(tmpl_doc, inc_doc)

    def compare_files(
        self,
        template_path: Path,
        incoming_path: Path,
    ) -> DiffReport:
        """Convenience method: compare two .docx files directly."""
        extractor = FieldExtractor()
        tmpl_doc = extractor.extract_from_file(template_path)
        inc_doc  = extractor.extract_from_file(incoming_path)
        return self.compare(tmpl_doc, inc_doc)

    # ── Private comparison logic ─────────────────────────────────────

    def _compare_fields(
        self,
        tmpl: ExtractedField,
        inc: ExtractedField,
    ) -> Discrepancy:
        """Compare two fields and return the appropriate Discrepancy."""

        # Both missing — match (both absent)
        if not tmpl.found and not inc.found:
            return Discrepancy(
                field_name=tmpl.name, field_key=tmpl.key,
                category=tmpl.category, risk_level=tmpl.risk_level,
                change_type=ChangeType.MATCH,
                template_value="", incoming_value="",
            )

        # Template has value, incoming missing
        if tmpl.found and not inc.found:
            return Discrepancy(
                field_name=tmpl.name, field_key=tmpl.key,
                category=tmpl.category, risk_level=tmpl.risk_level,
                change_type=ChangeType.MISSING,
                template_value=tmpl.value, incoming_value="",
                explanation=f"'{tmpl.name}' is present in template but missing in incoming document.",
            )

        # Incoming has value, template missing
        if not tmpl.found and inc.found:
            return Discrepancy(
                field_name=tmpl.name, field_key=tmpl.key,
                category=tmpl.category, risk_level=RiskLevel.LOW,
                change_type=ChangeType.ADDED,
                template_value="", incoming_value=inc.value,
                explanation=f"'{tmpl.name}' found in incoming but not in template.",
            )

        # Both have values — compare
        t_val = tmpl.value.strip()
        i_val = inc.value.strip()

        # Exact match (case-insensitive)
        if t_val.lower() == i_val.lower():
            return Discrepancy(
                field_name=tmpl.name, field_key=tmpl.key,
                category=tmpl.category, risk_level=tmpl.risk_level,
                change_type=ChangeType.MATCH,
                template_value=t_val, incoming_value=i_val,
            )

        # Try numeric comparison for economic fields
        if tmpl.category == "economic":
            numeric_result = self._compare_numeric(tmpl, inc, t_val, i_val)
            if numeric_result:
                return numeric_result

        # Text comparison with semantic similarity
        similarity = self._text_similarity(t_val, i_val)
        explanation = self._explain_change(tmpl.name, t_val, i_val, similarity)

        return Discrepancy(
            field_name=tmpl.name, field_key=tmpl.key,
            category=tmpl.category, risk_level=tmpl.risk_level,
            change_type=ChangeType.CHANGED,
            template_value=t_val, incoming_value=i_val,
            similarity=round(similarity, 3),
            explanation=explanation,
        )

    def _compare_numeric(
        self,
        tmpl: ExtractedField,
        inc: ExtractedField,
        t_val: str,
        i_val: str,
    ) -> Optional[Discrepancy]:
        """
        Extract numeric values and compare them.
        Returns a Discrepancy if both are numeric, None otherwise.
        """
        t_num = self._extract_number(t_val)
        i_num = self._extract_number(i_val)

        if t_num is None or i_num is None:
            return None  # Fall back to text comparison

        if t_num == 0:
            pct_change = 0.0 if i_num == 0 else float('inf')
        else:
            pct_change = abs((i_num - t_num) / t_num) * 100

        delta = i_num - t_num

        # Within tolerance — treat as match
        if pct_change <= self.NUMERIC_TOLERANCE_PCT * 100:
            return Discrepancy(
                field_name=tmpl.name, field_key=tmpl.key,
                category=tmpl.category, risk_level=tmpl.risk_level,
                change_type=ChangeType.MATCH,
                template_value=t_val, incoming_value=i_val,
                numeric_delta=round(delta, 6),
                numeric_pct=round(pct_change, 4),
            )

        direction = "increased" if delta > 0 else "decreased"
        explanation = (
            f"'{tmpl.name}' has {direction} by "
            f"{abs(pct_change):.2f}% "
            f"(template: {t_val}, incoming: {i_val}, delta: {delta:+.4f})."
        )

        return Discrepancy(
            field_name=tmpl.name, field_key=tmpl.key,
            category=tmpl.category, risk_level=tmpl.risk_level,
            change_type=ChangeType.NUMERIC_DRIFT,
            template_value=t_val, incoming_value=i_val,
            numeric_delta=round(delta, 6),
            numeric_pct=round(pct_change, 2),
            explanation=explanation,
        )

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        """
        Extract the primary numeric value from a field string.
        Handles: "USD 50,000,000", "4.25% per annum", "SOFR + 100bps", "5 year"
        """
        # Remove currency symbols and commas
        cleaned = re.sub(r"[£€$¥,]", "", text)
        # Find first number (including decimals)
        match = re.search(r"\d+(?:\.\d+)?", cleaned)
        if match:
            return float(match.group())
        return None

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """
        Simple token-based Jaccard similarity between two strings.
        Returns 0–1. (1 = identical, 0 = completely different)
        """
        tokens_a = set(re.sub(r"[^a-z0-9]", " ", a.lower()).split())
        tokens_b = set(re.sub(r"[^a-z0-9]", " ", b.lower()).split())
        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)

    @staticmethod
    def _explain_change(
        field_name: str,
        old_val: str,
        new_val: str,
        similarity: float,
    ) -> str:
        """Generate a human-readable explanation of the change."""
        if similarity > 0.8:
            return (f"'{field_name}' has minor wording difference "
                    f"(similarity: {similarity:.0%}): "
                    f"'{old_val}' → '{new_val}'")
        elif similarity > 0.4:
            return (f"'{field_name}' has been significantly modified "
                    f"(similarity: {similarity:.0%}): "
                    f"'{old_val}' → '{new_val}'")
        else:
            return (f"'{field_name}' has been completely changed "
                    f"(similarity: {similarity:.0%}): "
                    f"'{old_val}' → '{new_val}'")


# ─── Pretty Printer ───────────────────────────────────────────────────────

def print_diff_report(report: DiffReport) -> None:
    """Print a formatted diff report to the terminal."""
    print(f"\n{'═'*60}")
    print(f"  DIFFERENCE REPORT")
    print(f"  Template : {report.template_filename}")
    print(f"  Incoming : {report.incoming_filename}")
    print(f"{'═'*60}")
    print(f"  Risk Score: {report.risk_score:.0f}/100  |  "
          f"Needs Review: {'⚠ YES' if report.needs_review else '✅ NO'}")
    print(f"  🔴 {len(report.high_risk)} HIGH   "
          f"🟡 {len(report.medium_risk)} MEDIUM   "
          f"🟢 {len(report.low_risk)} LOW   "
          f"✅ {len(report.matches)} MATCH")

    if report.discrepancies:
        print(f"\n  {'─'*56}")
        print("  DISCREPANCIES")
        print(f"  {'─'*56}")
        for d in report.discrepancies:
            print(f"\n  {d.risk_icon} [{d.risk_level}] {d.change_icon} {d.field_name}  ({d.category})")
            print(f"     Template : {d.template_value or '(empty)'}")
            print(f"     Incoming : {d.incoming_value or '(empty)'}")
            if d.numeric_pct is not None:
                print(f"     Delta    : {d.numeric_pct:+.2f}%  ({d.numeric_delta:+.4f})")
            if d.similarity is not None:
                print(f"     Similarity: {d.similarity:.0%}")
            if d.explanation:
                print(f"     → {d.explanation}")

    if report.matches:
        print(f"\n  {'─'*56}")
        print(f"  MATCHING FIELDS ({len(report.matches)} identical)")
        print(f"  {'─'*56}")
        for m in report.matches:
            print(f"  ✅ {m.field_name}: {m.template_value[:60]}")

    print(f"\n{'═'*60}\n")


if __name__ == "__main__":
    from src.template_generator import generate_all_templates, TEMPLATES
    from src.diff.field_extractor import FieldExtractor
    from src.config import TEMPLATES_DIR

    generate_all_templates()
    extractor = FieldExtractor()
    engine    = DiffEngine()

    # Compare two IRS templates — v1 vs v2
    t1 = extractor.extract_from_file(TEMPLATES_DIR / "IRS_GoldmanSachs_USD_v1.docx")
    t2 = extractor.extract_from_file(TEMPLATES_DIR / "IRS_GoldmanSachs_USD_v2.docx")

    report = engine.compare(t1, t2)
    print_diff_report(report)

    # Compare IRS vs FX (should show many high-risk diffs)
    t3 = extractor.extract_from_file(TEMPLATES_DIR / "FX_Forward_JPMorgan_EUR_v1.docx")
    report2 = engine.compare(t1, t3)
    print_diff_report(report2)
