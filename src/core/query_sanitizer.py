import re

def sanitize_query(query: str) -> str:
    """
    Sanitize and validate a web search query.
    - Remove code block markers, brackets, and extraneous punctuation.
    - Remove empty or trivial queries.
    - Collapse whitespace.
    - Return an empty string if the query is not meaningful.
    """
    if not isinstance(query, str):
        return ""
    # Remove code block markers and brackets
    query = re.sub(r'[`{}\[\]"]', " ", query)
    # Remove excessive punctuation (except for . and ?)
    query = re.sub(r"[!@#$%^&*()_=+|;:'<>,/~]", " ", query)
    # Collapse whitespace
    query = re.sub(r"\s+", " ", query).strip()
    # Remove queries that are too short or not meaningful
    if len(query) < 3 or query.lower() in {"json", "queries", "ask_user", "query"}:
        return ""
    return query 