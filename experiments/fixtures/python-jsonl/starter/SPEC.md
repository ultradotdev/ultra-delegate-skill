# solution.py: JSON Lines totaller

`solution.py` is a command-line program run as `python3 solution.py`. It reads its
whole input from stdin and writes its result to stdout. Standard library only.

R1. Stdin is read as raw bytes and decoded as UTF-8. A single UTF-8 byte-order mark (EF BB BF) at the very start is ignored. Bytes that are not valid UTF-8 make the input invalid.
R2. The text is split into lines (the last line need not end with a newline). Lines that are empty or contain only whitespace are ignored.
R3. Every other line must hold exactly one JSON value, and that value must be a JSON object. Arrays, `null`, numbers, strings, booleans and malformed JSON are invalid.
R4. The object must have exactly the two keys `"name"` and `"count"`. A missing key, any extra key, or a key repeated within the same object (even with the same value) is invalid.
R5. `"name"` must be a nonempty JSON string.
R6. `"count"` must be a JSON integer from 0 to 1000000 inclusive. Booleans, numbers written with a fraction or exponent (such as `1.0`), strings and `null` are invalid, and so is any integer outside the range, however many digits it has.
R7. The non-standard literals `NaN`, `Infinity` and `-Infinity` are invalid.
R8. If the whole input is valid, the program writes exactly one JSON object `{"total": <sum of all counts>, "names": [<every name in input order, duplicates kept>]}` followed by one LF to stdout, writes nothing else to stdout, and exits with status 0. Input with no records (empty, or only blank lines) produces `{"total": 0, "names": []}`.
R9. Stdout is UTF-8 whatever the `PYTHONIOENCODING` environment variable says: with `PYTHONIOENCODING=latin1`, output containing non-ASCII names must still be valid UTF-8 JSON (`\u` escapes are acceptable).
R10. If any part of the input is invalid, the program writes no bytes at all to stdout (not even for earlier valid lines), writes a nonempty diagnostic message to stderr, and exits with status 2.
