"""Expected interruptions are command outcomes, not invalid-input failures."""


class MatchPaused(ValueError):
    """A match gate queued/retained a decision before any new map was played.

    Adapters acknowledge this as a successful paused command and persist its
    decision. Other ValueErrors must still roll back the entire operation.
    ValueError compatibility is retained for older desktop/CLI callers.
    """
