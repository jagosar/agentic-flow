"""Parsing of quantity text."""


def parse(text):
    """The quantity in text such as "3" or " 12 ", or None when the text is not a whole number."""
    text = text.strip()
    if not text.isdigit():
        return None
    return int(text)
