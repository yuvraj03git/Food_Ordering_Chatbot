def extract_session_id(session_str: str) -> str:
    """
    Extract the session ID from the Dialogflow session path.
    Example:
        input:  "projects/myproject/agent/sessions/abcd1234/contexts/ongoing-order"
        output: "abcd1234"
    """
    parts = session_str.split("/sessions/")
    if len(parts) > 1:
        session_and_context = parts[1]
        session_id = session_and_context.split("/contexts/")[0]
        return session_id
    return session_str  # fallback, if format is unexpected
