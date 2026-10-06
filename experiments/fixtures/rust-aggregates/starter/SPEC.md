# aggregates: group-by money totals over CSV-like text

Library crate `aggregates` (no dependencies):

- `src/parser.rs`: splitting lines into fields and reading the table (`parse_line`, `parse_table`).
- `src/aggregate.rs`: amounts and per-group totals.
- `src/format.rs`: money formatting and the output table (`format_cents`, `render`).
- `src/error.rs`: the `Error` type.
- `src/lib.rs`: `summarize(input: &str, group_col: &str, value_col: &str) -> Result<String, Error>`.

The tests use `aggregates::summarize`, `aggregates::Error`,
`aggregates::parser::parse_line(text: &str, line: usize) -> Result<Vec<String>, Error>` and
`aggregates::format::format_cents(cents: i64) -> String`. `Error` is:

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Error {
    Empty,
    UnterminatedQuote { line: usize },
    BadQuote { line: usize },
    DuplicateColumn(String),
    MissingColumn(String),
    FieldCount { line: usize, expected: usize, found: usize },
    BadAmount { line: usize, text: String },
    Overflow { group: String },
}
```

## Lines and fields

R1. The input is split into lines at `\n`, and a `\r` at the end of a line is removed. Lines are numbered from 1, counting every physical line including blank ones. A line that is empty or contains only spaces is skipped: it is neither the header nor a row.
R2. `parse_line(text, line)` splits one line into fields at commas. An unquoted field has its leading and trailing spaces removed (spaces only; tabs and other characters are kept).
R3. A field whose first non-space character is `"` is quoted. Its content runs to the closing `"`; inside it `,` is an ordinary character and `""` stands for one `"`. The content is kept exactly, including spaces inside the quotes. Spaces between the closing quote and the next comma or the end of the line are ignored.
R4. Field errors carry the line number passed to `parse_line`: a quoted field without a closing quote gives `UnterminatedQuote { line }`; anything other than spaces between a closing quote and the next comma or end of line gives `BadQuote { line }`; a `"` inside an unquoted field (after its first non-space character) gives `BadQuote { line }`.
R5. Empty fields are kept: `a,,b` has three fields, a line ending with `,` has an empty last field, `""` is an empty field, and an empty line is one empty field.

## Table

R6. The first non-blank line is the header and its fields are the column names. If there is no non-blank line the result is `Error::Empty`. If a name repeats, the result is `DuplicateColumn(name)` for the first field (left to right) whose name already appeared.
R7. Every later non-blank line is a data row and must have as many fields as the header, otherwise `FieldCount { line, expected, found }`.
R8. `group_col` and `value_col` must both be column names (exact, case-sensitive match), otherwise `MissingColumn(name)`; `group_col` is checked first.
R9. `summarize` returns the first error in this order: (1) `Empty`; (2) going through the lines in input order, the first field error (R4), `DuplicateColumn` (on the header line) or `FieldCount` (on a data line); (3) `MissingColumn` (R8); (4) going through the data rows in input order, the first row whose amount is invalid (`BadAmount`) or whose amount overflows its group's sum (`Overflow`).

## Amounts

R10. An amount field must be: an optional `-`, one or more ASCII digits, then optionally `.` followed by one or two ASCII digits. Its value is in cents: `7` is 700, `1.5` is 150, `0.05` is 5, `-0.05` is -5 and `-0` is 0. Leading zeros are allowed (`007.5` is 750). Anything else, for example `+1`, `.5`, `1.`, `1.234`, `--1`, a quoted `1,000` or a quoted ` 1` (the space is part of the content), gives `BadAmount { line, text }` where `text` is the field content.
R11. An amount whose value in cents does not fit in `i64` (outside `-92233720368547758.08` to `92233720368547758.07`) gives `BadAmount`.
R12. An empty amount field (unquoted, or `""`) means the row has no value. It is not zero.

## Aggregation

R13. Rows are grouped by the exact content of the group field after R2 and R3 (case- and space-sensitive): `north`, ` north ` (unquoted, so trimmed) and `North` give two groups, and a quoted `"north "` is a third.
R14. For each group: `rows` is the number of its rows, `values` the number of its rows that have a value, and `sum`, `min`, `max` and `mean` are computed over those values only.
R15. The sum is computed in `i64` cents, adding the group's values in input order with checked arithmetic: if any addition overflows, the result is `Overflow { group }` with the group key, even if later values would bring the total back into range.
R16. `mean` is the sum divided by `values`, rounded to the nearest cent with halves rounded away from zero (1.5 cents gives 2, -1.5 gives -2, -2.5 gives -3). It must be exact for every sum that fits in `i64`, so no floating point and no intermediate overflow.
R17. A group with no values has a sum of 0 and no `min`, `max` or `mean`.

## Output

R18. `format_cents(c)` is `-` when `c` is negative, then the whole part in decimal without leading zeros (at least one digit), then `.` and exactly two digits: 0 gives `0.00`, 5 gives `0.05`, -5 gives `-0.05`, -100 gives `-1.00` and 123456 gives `1234.56`. It works for every `i64`, including `i64::MIN` (`-92233720368547758.08`).
R19. The output is a header row followed by one row per group, with groups sorted by key in ascending byte order. The columns are, in order: the group key (its header is `group_col` itself), `rows`, `values`, `sum`, `min`, `max`, `mean`. Money is written with `format_cents`; a missing `min`, `max` or `mean` is written `-`. An empty group key is written `(empty)`.
R20. A column's width is the largest number of characters (`chars().count()`) among its header and its cells. The first column is left-aligned (padded with spaces on the right) and the others are right-aligned (padded on the left). Cells in a row are separated by two spaces. Every line, including the last, ends with `\n`, and no line has trailing spaces.
