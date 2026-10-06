use aggregates::format::format_cents;
use aggregates::parser::parse_line;
use aggregates::{summarize, Error};

#[test]
fn public_summary_table() {
    let input = "region,amount\nnorth,10.00\nsouth,5.5\nnorth,2.25\n";
    let expected = concat!(
        "region  rows  values    sum   min    max  mean\n",
        "north      2       2  12.25  2.25  10.00  6.13\n",
        "south      1       1   5.50  5.50   5.50  5.50\n",
    );
    assert_eq!(summarize(input, "region", "amount").unwrap(), expected);
}

#[test]
fn public_quoted_comma() {
    let input = "name,amount\n\"Smith, J\",10.00\nLee,2.00\n";
    let expected = concat!(
        "name      rows  values    sum    min    max   mean\n",
        "Lee          1       1   2.00   2.00   2.00   2.00\n",
        "Smith, J     1       1  10.00  10.00  10.00  10.00\n",
    );
    assert_eq!(summarize(input, "name", "amount").unwrap(), expected);
}

#[test]
fn public_parse_line() {
    assert_eq!(parse_line("a, b ,c", 1).unwrap(), vec!["a", "b", "c"]);
}

#[test]
fn public_format_cents() {
    assert_eq!(format_cents(123456), "1234.56");
    assert_eq!(format_cents(5), "0.05");
    assert_eq!(format_cents(0), "0.00");
}

#[test]
fn public_missing_column() {
    assert_eq!(summarize("g,a\nx,1\n", "h", "a"), Err(Error::MissingColumn("h".to_string())));
}
