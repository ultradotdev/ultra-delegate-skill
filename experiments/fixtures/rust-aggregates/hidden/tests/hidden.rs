use aggregates::format::format_cents;
use aggregates::parser::parse_line;
use aggregates::{summarize, Error};

fn strings(v: &[&str]) -> Vec<String> {
    v.iter().map(|s| s.to_string()).collect()
}

/// Data rows of a rendered table split on whitespace (keys in these tests contain no spaces).
fn data_rows(out: &str) -> Vec<Vec<String>> {
    out.lines().skip(1).map(|l| l.split_whitespace().map(String::from).collect()).collect()
}

fn ok(input: &str) -> Vec<Vec<String>> {
    data_rows(&summarize(input, "g", "a").expect("summarize failed"))
}

fn bad_amount(line: usize, text: &str) -> Error {
    Error::BadAmount { line, text: text.to_string() }
}

const MAX: &str = "92233720368547758.07";
const MIN: &str = "-92233720368547758.08";

// R1
#[test]
fn line_endings_blank_lines_and_numbering() {
    assert_eq!(
        ok("g,a\r\n\r\n   \nx,1\r\ny,2\n\n"),
        vec![strings(&["x", "1", "1", "1.00", "1.00", "1.00", "1.00"]), strings(&["y", "1", "1", "2.00", "2.00", "2.00", "2.00"])]
    );
    assert_eq!(summarize("g,a\n\n  \nx,1,2\n", "g", "a"), Err(Error::FieldCount { line: 4, expected: 2, found: 3 }));
    assert_eq!(summarize("\n\ng,a\nx,oops\n", "g", "a"), Err(bad_amount(4, "oops")));
}

// R2
#[test]
fn unquoted_fields_trim_spaces_only() {
    assert_eq!(parse_line("  a b  ,\tc\t, d", 1).unwrap(), strings(&["a b", "\tc\t", "d"]));
    assert_eq!(ok("g,a\n  x  ,  1.25  \n"), vec![strings(&["x", "1", "1", "1.25", "1.25", "1.25", "1.25"])]);
}

// R3
#[test]
fn quoted_fields_keep_content() {
    assert_eq!(
        parse_line("\"a, \"\"b\"\" c\",  \" x \"  ,\"\" ", 9).unwrap(),
        strings(&["a, \"b\" c", " x ", ""])
    );
    assert_eq!(parse_line("\"\"\"\"", 1).unwrap(), strings(&["\""]));
    assert_eq!(parse_line(" \"a\" , b", 1).unwrap(), strings(&["a", "b"]));
}

// R4
#[test]
fn field_errors() {
    assert_eq!(parse_line("\"abc", 7), Err(Error::UnterminatedQuote { line: 7 }));
    assert_eq!(parse_line("x,\"a\"\"", 5), Err(Error::UnterminatedQuote { line: 5 }));
    assert_eq!(parse_line("\"a\"x,b", 3), Err(Error::BadQuote { line: 3 }));
    assert_eq!(parse_line("x,\"a\" b", 1), Err(Error::BadQuote { line: 1 }));
    assert_eq!(parse_line("a\"b,c", 2), Err(Error::BadQuote { line: 2 }));
    assert_eq!(summarize("g,a\n\nx,\"1\n", "g", "a"), Err(Error::UnterminatedQuote { line: 3 }));
}

// R5
#[test]
fn empty_fields_are_kept() {
    assert_eq!(parse_line("a,,b", 1).unwrap(), strings(&["a", "", "b"]));
    assert_eq!(parse_line("a,", 1).unwrap(), strings(&["a", ""]));
    assert_eq!(parse_line(" , ", 1).unwrap(), strings(&["", ""]));
    assert_eq!(parse_line("\"\"", 1).unwrap(), strings(&[""]));
    assert_eq!(parse_line("", 1).unwrap(), strings(&[""]));
}

// R6
#[test]
fn header_rules() {
    assert_eq!(summarize("", "g", "a"), Err(Error::Empty));
    assert_eq!(summarize("\n   \r\n\n", "g", "a"), Err(Error::Empty));
    assert_eq!(summarize("g,a,g\n", "g", "a"), Err(Error::DuplicateColumn("g".into())));
    assert_eq!(summarize("a,b,b,a\n", "a", "b"), Err(Error::DuplicateColumn("b".into())));
    assert_eq!(summarize("\n\"g\",\"a\"\n", "g", "a").unwrap(), "g  rows  values  sum  min  max  mean\n");
}

// R7
#[test]
fn field_count() {
    assert_eq!(summarize("g,a\nx,1\ny\n", "g", "a"), Err(Error::FieldCount { line: 3, expected: 2, found: 1 }));
    assert_eq!(summarize("g,a\nx,1,\n", "g", "a"), Err(Error::FieldCount { line: 2, expected: 2, found: 3 }));
    assert_eq!(ok("g,a\n\"x,y\",1\n"), vec![strings(&["x,y", "1", "1", "1.00", "1.00", "1.00", "1.00"])]);
}

// R8
#[test]
fn missing_columns() {
    let input = "g,a\nx,1\n";
    assert_eq!(summarize(input, "h", "a"), Err(Error::MissingColumn("h".into())));
    assert_eq!(summarize(input, "g", "b"), Err(Error::MissingColumn("b".into())));
    assert_eq!(summarize(input, "h", "b"), Err(Error::MissingColumn("h".into())));
    assert_eq!(summarize(input, "G", "a"), Err(Error::MissingColumn("G".into())));
}

// R9
#[test]
fn error_order() {
    assert_eq!(summarize("g,a\nx,bad\ny,1\nz\n", "g", "a"), Err(Error::FieldCount { line: 4, expected: 2, found: 1 }));
    assert_eq!(summarize("g,a\nx,1\n\"y\n", "g", "nope"), Err(Error::UnterminatedQuote { line: 3 }));
    assert_eq!(summarize("g,a\nx,bad\n", "nope", "a"), Err(Error::MissingColumn("nope".into())));
    assert_eq!(summarize(&format!("g,a\nx,{MAX}\ny,bad\nx,1\n"), "g", "a"), Err(bad_amount(3, "bad")));
    assert_eq!(summarize(&format!("g,a\nx,{MAX}\nx,1\ny,bad\n"), "g", "a"), Err(Error::Overflow { group: "x".into() }));
}

// R10
#[test]
fn amount_grammar() {
    let rows = ok("g,a\nb,7\nc,1.5\nd,0.05\ne,-0.05\nf,-0\ng,007.5\nh,12.34\n");
    let sums: Vec<(&str, &str)> = rows.iter().map(|r| (r[0].as_str(), r[3].as_str())).collect();
    assert_eq!(
        sums,
        vec![("b", "7.00"), ("c", "1.50"), ("d", "0.05"), ("e", "-0.05"), ("f", "0.00"), ("g", "7.50"), ("h", "12.34")]
    );
    let invalid = [
        ("+1", "+1"),
        (".5", ".5"),
        ("1.", "1."),
        ("1.234", "1.234"),
        ("--1", "--1"),
        ("-", "-"),
        ("1.2.3", "1.2.3"),
        ("abc", "abc"),
        ("1 000", "1 000"),
        ("\"1,000\"", "1,000"),
        ("\" 1\"", " 1"),
        ("\"2 \"", "2 "),
        ("\u{ff11}", "\u{ff11}"),
    ];
    for (field, text) in invalid {
        let input = format!("g,a\nx,1\ny,{field}\n");
        assert_eq!(summarize(&input, "g", "a"), Err(bad_amount(3, text)), "amount field {field:?}");
    }
}

// R11
#[test]
fn amount_range() {
    let rows = ok(&format!("g,a\nhi,{MAX}\nlo,{MIN}\nz,000000000000000000000000001\n"));
    assert_eq!(rows[0][3], MAX);
    assert_eq!(rows[1][3], MIN);
    assert_eq!(rows[2][3], "1.00");
    for field in ["92233720368547758.08", "-92233720368547758.09", "99999999999999999999999999", "-100000000000000000000000000000.00"] {
        let input = format!("g,a\nx,{field}\n");
        assert_eq!(summarize(&input, "g", "a"), Err(bad_amount(2, field)), "amount field {field:?}");
    }
}

// R12
#[test]
fn empty_amount_is_no_value() {
    assert_eq!(
        ok("g,a\nx,\nx,4\ny,\nz,\"\"\nz,-1\n"),
        vec![
            strings(&["x", "2", "1", "4.00", "4.00", "4.00", "4.00"]),
            strings(&["y", "1", "0", "0.00", "-", "-", "-"]),
            strings(&["z", "2", "1", "-1.00", "-1.00", "-1.00", "-1.00"]),
        ]
    );
}

// R13
#[test]
fn groups_by_exact_field_content() {
    let out = summarize("g,a\nnorth,1\n\"north \",2\nNorth,3\n north ,4\n", "g", "a").unwrap();
    let expected = concat!(
        "g       rows  values   sum   min   max  mean\n",
        "North      1       1  3.00  3.00  3.00  3.00\n",
        "north      2       2  5.00  1.00  4.00  2.50\n",
        "north      1       1  2.00  2.00  2.00  2.00\n",
    );
    assert_eq!(out, expected);
}

// R14
#[test]
fn values_min_max_mean_skip_rows_without_values() {
    assert_eq!(ok("g,a\nk,3.00\nk,\nk,-1.25\nk,10\n"), vec![strings(&["k", "4", "3", "11.75", "-1.25", "10.00", "3.92"])]);
}

// R15
#[test]
fn checked_sum() {
    assert_eq!(summarize(&format!("g,a\nbig,{MAX}\nbig,0.01\n"), "g", "a"), Err(Error::Overflow { group: "big".into() }));
    assert_eq!(
        summarize(&format!("g,a\nbig,{MAX}\nbig,0.01\nbig,-1.00\n"), "g", "a"),
        Err(Error::Overflow { group: "big".into() })
    );
    assert_eq!(summarize(&format!("g,a\nneg,{MIN}\nneg,-0.01\n"), "g", "a"), Err(Error::Overflow { group: "neg".into() }));
    let rows = ok(&format!("g,a\na,{MAX}\nb,{MAX}\na,-0.07\na,0.07\n"));
    assert_eq!(rows[0][3], MAX);
    assert_eq!(rows[1][3], MAX);
}

// R16
#[test]
fn mean_rounds_half_away_from_zero() {
    let rows = ok("g,a\na,0.01\na,0.02\nb,-0.01\nb,-0.02\nc,-0.05\nc,0\nd,0.01\nd,0.01\nd,0.02\ne,-0.02\ne,-0.02\ne,-0.01\n");
    let means: Vec<&str> = rows.iter().map(|r| r[6].as_str()).collect();
    assert_eq!(means, vec!["0.02", "-0.02", "-0.03", "0.01", "-0.02"]);
}

// R16
#[test]
fn mean_is_exact_for_extreme_sums() {
    let rows = ok(&format!(
        "g,a\nhi,92233720368547758.06\nhi,0.01\nlo,-92233720368547758.07\nlo,-0.01\none,{MIN}\nthird,{MAX}\nthird,-0.07\nthird,0.07\n"
    ));
    assert_eq!(rows[0][6], "46116860184273879.04");
    assert_eq!(rows[1][6], "-46116860184273879.04");
    assert_eq!(rows[2][6], MIN);
    assert_eq!(rows[3][6], "30744573456182586.02");
}

// R17
#[test]
fn group_without_values() {
    assert_eq!(ok("g,a\nonly,\nonly,\"\"\n"), vec![strings(&["only", "2", "0", "0.00", "-", "-", "-"])]);
}

// R18
#[test]
fn format_cents_values() {
    let cases = [
        (0, "0.00"),
        (5, "0.05"),
        (10, "0.10"),
        (100, "1.00"),
        (123456, "1234.56"),
        (-1, "-0.01"),
        (-5, "-0.05"),
        (-99, "-0.99"),
        (-100, "-1.00"),
        (-123456, "-1234.56"),
        (i64::MAX, MAX),
        (i64::MIN, MIN),
    ];
    for (cents, text) in cases {
        assert_eq!(format_cents(cents), text, "format_cents({cents})");
    }
}

// R19
#[test]
fn output_columns_and_order() {
    let out = summarize("k,v\nb,1\nB,2\na,\n,3\n\u{e9},4\n", "k", "v").unwrap();
    let lines: Vec<&str> = out.lines().collect();
    assert_eq!(lines[0].split_whitespace().collect::<Vec<_>>(), vec!["k", "rows", "values", "sum", "min", "max", "mean"]);
    let keys: Vec<&str> = lines[1..].iter().map(|l| l.split_whitespace().next().unwrap()).collect();
    assert_eq!(keys, vec!["(empty)", "B", "a", "b", "\u{e9}"]);
    assert_eq!(lines[3].split_whitespace().collect::<Vec<_>>(), vec!["a", "1", "0", "0.00", "-", "-", "-"]);
}

// R20
#[test]
fn alignment_and_widths() {
    let out = summarize("city,amount\nZ\u{fc}rich,-1234.5\nOslo,0.5\nOslo,\n", "city", "amount").unwrap();
    let expected = concat!(
        "city    rows  values       sum       min       max      mean\n",
        "Oslo       2       1      0.50      0.50      0.50      0.50\n",
        "Z\u{fc}rich     1       1  -1234.50  -1234.50  -1234.50  -1234.50\n",
    );
    assert_eq!(out, expected);
    assert_eq!(
        summarize("k,v\n,1\n", "k", "v").unwrap(),
        "k        rows  values   sum   min   max  mean\n(empty)     1       1  1.00  1.00  1.00  1.00\n"
    );
}
