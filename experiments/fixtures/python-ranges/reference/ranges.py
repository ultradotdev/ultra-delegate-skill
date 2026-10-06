def parse_ranges(text):
    if not text.strip():
        return []
    result = set()
    for token in text.split(','):
        parts = [p.strip() for p in token.split('-')]
        if len(parts) > 2 or any(not (p.isascii() and p.isdigit()) for p in parts):
            raise ValueError(f'invalid token: {token!r}')
        start, end = int(parts[0]), int(parts[-1])
        if start > end:
            raise ValueError(f'reversed range: {token!r}')
        result.update(range(start, end + 1))
    return sorted(result)
