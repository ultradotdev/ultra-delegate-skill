# parse_ranges(text: str) -> list[int]

Parse a comma-separated list of integer ranges.

R1. Each token is either a single integer `N` or an inclusive range `A-B`; the result includes every integer from A to B, both ends included.
R2. The result is sorted ascending with duplicates removed.
R3. Whitespace around a token or around its parts is ignored.
R4. Empty or whitespace-only input returns an empty list.
R5. Integers consist of ASCII digits only; signs, non-ASCII digits and other characters raise ValueError.
R6. An empty token (such as a trailing comma) raises ValueError.
R7. A token with more than one `-` raises ValueError.
R8. A range whose start is greater than its end raises ValueError.
