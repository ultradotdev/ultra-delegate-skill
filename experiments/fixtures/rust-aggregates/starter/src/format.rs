use crate::aggregate::Summary;

/// Formats cents as `[-]units.cc`.
pub fn format_cents(cents: i64) -> String {
    format!("{}.{:02}", cents / 100, (cents % 100).abs())
}

/// Renders the summaries as a table: first column left-aligned, the others
/// right-aligned, two spaces between columns.
pub fn render(group_col: &str, summaries: &[Summary]) -> String {
    let mut table: Vec<Vec<String>> = vec![[group_col, "rows", "values", "sum", "min", "max", "mean"]
        .iter()
        .map(|s| s.to_string())
        .collect()];
    for s in summaries {
        let key = if s.key.is_empty() { "(empty)".to_string() } else { s.key.clone() };
        table.push(vec![
            key,
            s.rows.to_string(),
            s.values.to_string(),
            format_cents(s.sum),
            format_cents(s.min),
            format_cents(s.max),
            format_cents(s.mean),
        ]);
    }
    let widths: Vec<usize> =
        (0..7).map(|c| table.iter().map(|row| row[c].chars().count()).max().unwrap_or(0)).collect();
    let mut out = String::new();
    for row in &table {
        let cells: Vec<String> = row
            .iter()
            .enumerate()
            .map(|(c, cell)| {
                if c == 0 {
                    format!("{:<w$}", cell, w = widths[c])
                } else {
                    format!("{:>w$}", cell, w = widths[c])
                }
            })
            .collect();
        out.push_str(&cells.join("  "));
        out.push('\n');
    }
    out
}
