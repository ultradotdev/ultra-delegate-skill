# parse_counts(text: str) -> dict

`solution.py` defines `parse_counts`, which parses CSV text holding a header and
`name,count` data records. Standard library only.

R1. The first record is the header and must be exactly the two fields `name` and `count`. A missing header (including empty input) or any other header raises ValueError.
R2. Records may end with LF or CRLF, and one Unicode BOM (U+FEFF) at the very start of the text is ignored.
R3. Standard CSV double-quote quoting applies: a quoted field may contain commas, doubled quotes (`""` stands for one `"`) and embedded newlines (LF or CRLF), all kept verbatim in the field value.
R4. Malformed CSV, such as a quoted field that is never closed, raises ValueError.
R5. Completely blank physical lines (empty lines) are ignored wherever they appear; they are not records.
R6. The result is `{"rows": [...], "errors": [...]}`. Each valid data record becomes `{"name": str, "count": int}` in `rows`, in input order.
R7. A data record must have exactly two columns; any other number of columns makes the record invalid.
R8. The name (first column) must be nonempty. Its whitespace is preserved exactly: names are never stripped.
R9. The count (second column) must be one or more ASCII digits `0`-`9`, optionally preceded and/or followed by spaces and tabs. Signs, decimal points, exponents, non-ASCII digits, whitespace between digits or any other character make the record invalid.
R10. The count must represent an integer from 0 to 1000000 inclusive. Leading zeros are allowed and the field may be arbitrarily long (5000 zeros followed by `2` is the count 2); a value above 1000000 makes the record invalid.
R11. An invalid data record is left out of `rows`, its index is appended to `errors` (in input order), and parsing continues with the following records. Data records are numbered from 1 in input order; the header and blank lines are not numbered.
