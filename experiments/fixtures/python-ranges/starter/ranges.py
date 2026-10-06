def parse_ranges(text):
    result = set()
    for part in text.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            result.update(range(start, end))
        else:
            result.add(int(part))
    return sorted(result)
