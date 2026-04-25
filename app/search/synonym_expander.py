"""Domain synonym expansion."""

from app.search.normalizer import normalize_query

WEALTHTECH_SYNONYMS: dict[str, tuple[str, ...]] = {
    "address proof": (
        "utility bill",
        "bank statement",
        "lease agreement",
        "proof of residence",
        "residence proof",
    ),
    "id proof": (
        "passport",
        "driver license",
        "national id",
        "identity document",
    ),
    "income proof": (
        "payslip",
        "salary slip",
        "tax return",
        "employment letter",
    ),
    "bank proof": (
        "bank statement",
        "account statement",
        "IBAN document",
    ),
}


def expand_synonyms(query: str, *, include_original: bool = True) -> list[str]:
    """Return deterministic domain-specific synonym expansion for a query."""
    normalized_query = normalize_query(query)
    expansions: list[str] = []

    if include_original and normalized_query:
        expansions.append(normalized_query)

    for key, synonyms in WEALTHTECH_SYNONYMS.items():
        if key in normalized_query:
            expansions.extend(normalize_query(synonym) for synonym in synonyms)

    return list(dict.fromkeys(expansions))

