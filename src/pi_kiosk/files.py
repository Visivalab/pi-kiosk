def upsert_marked_block(original: str, begin: str, end: str, body: str) -> str:
    """Insert or replace a tagged block. Leaves every other line alone."""
    block = f"{begin}\n{body.rstrip()}\n{end}\n"
    if begin in original and end in original:
        pre, rest = original.split(begin, 1)
        _, post = rest.split(end, 1)
        if post.startswith("\n"):
            post = post[1:]
        return pre + block + post
    if original and not original.endswith("\n"):
        original += "\n"
    return original + block


def read_or_empty(host, path: str) -> str:
    if not host.exists(path):
        return ""
    return host.read_file(path)
