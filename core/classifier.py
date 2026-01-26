"""
Document classifier with scoring-based detection.
Supports keyword matching, pattern matching, and weighted scoring.
"""
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClassificationRule:
    """A single classification rule with weight."""
    pattern: str
    weight: float = 1.0
    is_regex: bool = False
    case_sensitive: bool = False


@dataclass
class ClassificationResult:
    """Result of document classification."""
    template_code: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    matched_rules: list[str] = field(default_factory=list)


@dataclass
class TemplateClassifier:
    """Classifier configuration for a template."""
    code: str
    doc_type: str
    keywords: list[str] = field(default_factory=list)
    patterns: list[ClassificationRule] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    min_confidence: float = 0.3
    priority: int = 0


class DocumentClassifier:
    """
    Multi-strategy document classifier.

    Scoring:
    - Exact keyword match: 1.0 * weight
    - Partial match: 0.5 * weight
    - Regex pattern match: 1.0 * weight
    - Negative keyword: -0.5 per match

    Final confidence = total_score / max_possible_score
    """

    def __init__(self, templates: list[TemplateClassifier] | None = None):
        self.templates = templates or []
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for efficiency."""
        for template in self.templates:
            for rule in template.patterns:
                if rule.is_regex:
                    flags = 0 if rule.case_sensitive else re.IGNORECASE
                    rule._compiled = re.compile(rule.pattern, flags)

    def add_template(self, template: TemplateClassifier):
        """Add a template classifier."""
        self.templates.append(template)
        # Compile patterns for the new template
        for rule in template.patterns:
            if rule.is_regex:
                flags = 0 if rule.case_sensitive else re.IGNORECASE
                rule._compiled = re.compile(rule.pattern, flags)

    def classify(self, text: str) -> ClassificationResult | None:
        """
        Classify document text against all templates.

        Returns the best matching template or None if no match exceeds min_confidence.
        """
        if not text or not self.templates:
            return None

        text_upper = text.upper()
        results = []

        for template in self.templates:
            score, matched_rules = self._score_template(text, text_upper, template)
            max_score = self._calculate_max_score(template)

            confidence = score / max_score if max_score > 0 else 0.0
            confidence = min(1.0, max(0.0, confidence))  # Clamp to [0, 1]

            if confidence >= template.min_confidence:
                results.append(ClassificationResult(
                    template_code=template.code,
                    confidence=confidence,
                    scores={template.code: score},
                    matched_rules=matched_rules,
                ))

        if not results:
            return None

        # Sort by confidence (desc) then priority (desc)
        results.sort(key=lambda r: (
            r.confidence,
            next((t.priority for t in self.templates if t.code == r.template_code), 0)
        ), reverse=True)

        return results[0]

    def classify_all(self, text: str) -> list[ClassificationResult]:
        """
        Classify and return all matching templates sorted by confidence.
        """
        if not text or not self.templates:
            return []

        text_upper = text.upper()
        results = []

        for template in self.templates:
            score, matched_rules = self._score_template(text, text_upper, template)
            max_score = self._calculate_max_score(template)

            confidence = score / max_score if max_score > 0 else 0.0
            confidence = min(1.0, max(0.0, confidence))

            results.append(ClassificationResult(
                template_code=template.code,
                confidence=confidence,
                scores={template.code: score},
                matched_rules=matched_rules,
            ))

        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def _score_template(
        self, text: str, text_upper: str, template: TemplateClassifier
    ) -> tuple[float, list[str]]:
        """Calculate score for a single template."""
        score = 0.0
        matched_rules = []

        # Keyword matching
        for keyword in template.keywords:
            kw_upper = keyword.upper()
            if kw_upper in text_upper:
                score += 1.0
                matched_rules.append(f"keyword:{keyword}")
            elif any(word in text_upper for word in kw_upper.split()):
                # Partial match for multi-word keywords
                score += 0.3
                matched_rules.append(f"partial:{keyword}")

        # Pattern matching
        for rule in template.patterns:
            if rule.is_regex:
                compiled = getattr(rule, '_compiled', None)
                if compiled and compiled.search(text):
                    score += rule.weight
                    matched_rules.append(f"pattern:{rule.pattern[:30]}")
            else:
                search_text = text if rule.case_sensitive else text_upper
                search_pattern = rule.pattern if rule.case_sensitive else rule.pattern.upper()
                if search_pattern in search_text:
                    score += rule.weight
                    matched_rules.append(f"pattern:{rule.pattern[:30]}")

        # Negative keywords (reduce score)
        for neg_kw in template.negative_keywords:
            if neg_kw.upper() in text_upper:
                score -= 0.5
                matched_rules.append(f"negative:{neg_kw}")

        return max(0, score), matched_rules

    def _calculate_max_score(self, template: TemplateClassifier) -> float:
        """Calculate maximum possible score for a template."""
        max_score = len(template.keywords)  # Each keyword = 1.0
        max_score += sum(rule.weight for rule in template.patterns)
        return max(1.0, max_score)  # Minimum of 1 to avoid division by zero


def build_classifier_from_templates(templates: list[dict]) -> DocumentClassifier:
    """
    Build a classifier from template dictionaries.

    Expected format:
    {
        "code": "factura",
        "doc_type": "factura",
        "classification_keywords": ["FACTURA ELECTRÓNICA", ...],
        "classification_patterns": [{"pattern": "...", "weight": 1.0, "is_regex": true}],
        "negative_keywords": ["ANULADA"],
        "priority": 10,
    }
    """
    classifier = DocumentClassifier()

    for t in templates:
        patterns = []
        for p in t.get("classification_patterns", []):
            patterns.append(ClassificationRule(
                pattern=p.get("pattern", ""),
                weight=p.get("weight", 1.0),
                is_regex=p.get("is_regex", False),
                case_sensitive=p.get("case_sensitive", False),
            ))

        template = TemplateClassifier(
            code=t.get("code", ""),
            doc_type=t.get("doc_type", "otro"),
            keywords=t.get("classification_keywords", []),
            patterns=patterns,
            negative_keywords=t.get("negative_keywords", []),
            priority=t.get("priority", 0),
        )
        classifier.add_template(template)

    return classifier


# Default classification rules for Chilean documents
DEFAULT_CLASSIFIERS = [
    TemplateClassifier(
        code="factura",
        doc_type="factura",
        keywords=[
            "FACTURA ELECTRÓNICA",
            "FACTURA ELECTRONICA",
            "FACTURA AFECTA",
            "R.U.T. RECEPTOR",
            "RUT RECEPTOR",
        ],
        patterns=[
            ClassificationRule(r"FACTURA\s+(ELECTR[OÓ]NICA|AFECTA)", weight=2.0, is_regex=True),
            ClassificationRule(r"S\.?I\.?I\.?", weight=0.5, is_regex=True),
        ],
        negative_keywords=["BOLETA", "GUÍA DE DESPACHO", "NOTA DE CRÉDITO"],
        priority=10,
    ),
    TemplateClassifier(
        code="boleta",
        doc_type="boleta",
        keywords=[
            "BOLETA ELECTRÓNICA",
            "BOLETA ELECTRONICA",
            "BOLETA DE VENTAS",
        ],
        patterns=[
            ClassificationRule(r"BOLETA\s+(ELECTR[OÓ]NICA|DE\s+VENTAS)", weight=2.0, is_regex=True),
        ],
        negative_keywords=["FACTURA", "GUÍA DE DESPACHO"],
        priority=10,
    ),
    TemplateClassifier(
        code="guia_despacho",
        doc_type="guia_despacho",
        keywords=[
            "GUÍA DE DESPACHO",
            "GUIA DE DESPACHO",
            "GUÍA ELECTRÓNICA",
        ],
        patterns=[
            ClassificationRule(r"GU[IÍ]A\s+DE\s+DESPACHO", weight=2.0, is_regex=True),
        ],
        negative_keywords=["FACTURA", "BOLETA"],
        priority=10,
    ),
    TemplateClassifier(
        code="nota_credito",
        doc_type="nota_credito",
        keywords=[
            "NOTA DE CRÉDITO",
            "NOTA DE CREDITO",
            "NOTA CRÉDITO ELECTRÓNICA",
        ],
        patterns=[
            ClassificationRule(r"NOTA\s+(DE\s+)?CR[EÉ]DITO", weight=2.0, is_regex=True),
        ],
        negative_keywords=["FACTURA", "BOLETA"],
        priority=10,
    ),
]


def get_default_classifier() -> DocumentClassifier:
    """Get classifier with default Chilean document rules."""
    return DocumentClassifier(DEFAULT_CLASSIFIERS)
