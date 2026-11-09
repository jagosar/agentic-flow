"""A tiny store of user names."""

NAMES = []


def save(name):
    """Stores a user name once it is clean."""
    NAMES.append(clean(name))
    return NAMES[-1]


def clean(name):
    """A name of 1 to 40 letters, digits, spaces or hyphens; anything else is refused."""
    if not isinstance(name, str):
        raise TypeError("name must be text")
    name = name.strip()
    if not 1 <= len(name) <= 40 or not all(ch.isalnum() or ch in " -" for ch in name):
        raise ValueError(f"invalid name: {name!r}")
    return name
