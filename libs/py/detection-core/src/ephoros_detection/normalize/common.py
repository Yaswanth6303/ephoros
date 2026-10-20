from datetime import datetime


class NormalizationError(ValueError):
    """A raw record that cannot become an Event; the message is the DLQ reason."""


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)  # accepts a trailing Z; naive values fail Event validation
