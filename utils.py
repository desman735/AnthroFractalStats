
def format_reply(line: str, prefix: str = "- ") -> str:
    line = line.replace("\n", " ⮒ ")
    return f"{prefix}{line}"
