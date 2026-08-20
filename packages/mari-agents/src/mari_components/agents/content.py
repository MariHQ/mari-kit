"""Boundaries for treating retrieved content as data rather than instructions."""

UNTRUSTED_OPEN = "<<<UNTRUSTED_DOCUMENT_CONTENT>>>"
UNTRUSTED_CLOSE = "<<<END_UNTRUSTED_DOCUMENT_CONTENT>>>"


def safe_document_body(value: str) -> str:
    return value.replace(UNTRUSTED_OPEN, "[document delimiter removed]").replace(
        UNTRUSTED_CLOSE, "[document delimiter removed]",
    )


def untrusted_document(value: str) -> str:
    return f"{UNTRUSTED_OPEN}\n{safe_document_body(value)}\n{UNTRUSTED_CLOSE}"
