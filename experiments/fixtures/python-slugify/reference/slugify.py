import re
import unicodedata


def slugify(text, max_length=None):
    if max_length is not None and max_length < 1:
        raise ValueError('max_length must be at least 1')
    decomposed = unicodedata.normalize('NFKD', text)
    plain = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    slug = re.sub(r'[^a-z0-9]+', '-', plain.lower()).strip('-')
    if max_length is not None:
        slug = slug[:max_length].rstrip('-')
    return slug
