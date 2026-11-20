"""Domain errors shared by services and HTTP response mapping."""


class ResourceNotFound(ValueError):
    """The requested domain record does not exist."""
