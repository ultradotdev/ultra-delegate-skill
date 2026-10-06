# slugify(text: str, max_length: int | None = None) -> str

`slugify.py` defines `slugify`, which turns arbitrary text into a URL slug. Standard
library only.

R1. The result contains only lowercase ASCII letters `a`-`z`, ASCII digits `0`-`9` and hyphens `-`.
R2. ASCII letters are lowercased; ASCII letters and digits are otherwise kept in order.
R3. Every maximal run of characters that are not ASCII letters or digits (spaces, punctuation, hyphens, underscores, emoji, non-ASCII digits, and so on) becomes a single hyphen.
R4. The result never starts or ends with a hyphen.
R5. Text containing no ASCII letters or digits (after R6) returns the empty string.
R6. Before anything else, the text is normalized with Unicode NFKD and every combining character (`unicodedata.combining(ch) != 0`) is deleted, so `"Café"` becomes `"cafe"` and the ligature `"ﬁ"` becomes `"fi"`. Characters that are still not ASCII letters or digits after this step are separators under R3 (for example `"ß"`).
R7. When `max_length` is an integer, the slug produced by R1-R6 is cut to its first `max_length` characters and any hyphens left at the end by the cut are removed. `max_length=None` (the default) means no limit.
R8. A `max_length` less than 1 raises ValueError.
