"""Renders a stored chat history for the API, tagging recorded answers."""


def serialise_history(history, ids_by_answer):
    """Turns stored messages into payloads, adding `interactionId`.

    Answers are matched to interactions by their text rather than by
    position. A failed interaction is recorded but never written to the
    chat history, so the two sequences drift apart after the first error
    and index-based pairing would attribute ratings to the wrong answer.

    An answer with no match keeps `interactionId: None`, which the client
    reads as "not rateable".
    """
    available = {answer: list(ids) for answer, ids in ids_by_answer.items()}

    messages = []
    for message in getattr(history, "messages", None) or []:
        content = getattr(message, "content", "")
        payload = {
            "type": getattr(message, "type", None),
            "content": content,
        }
        if payload["type"] == "ai":
            pending = available.get(content)
            payload["interactionId"] = pending.pop(0) if pending else None
        messages.append(payload)

    return messages
