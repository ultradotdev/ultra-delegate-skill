//! Group-by money totals over CSV-like text.

pub mod aggregate;
pub mod error;
pub mod format;
pub mod parser;

pub use error::Error;

/// Parses `input`, groups its rows by `group_col`, totals `value_col` and
/// renders the result as an aligned text table.
pub fn summarize(input: &str, group_col: &str, value_col: &str) -> Result<String, Error> {
    let table = parser::parse_table(input)?;
    let summaries = aggregate::aggregate(&table, group_col, value_col)?;
    Ok(format::render(group_col, &summaries))
}
