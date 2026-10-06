use std::fmt;

/// Everything that can go wrong while summarizing.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Error {
    /// The input has no non-blank line, so there is no header.
    Empty,
    /// A quoted field is not closed before the end of its line.
    UnterminatedQuote { line: usize },
    /// A quote character where none is allowed.
    BadQuote { line: usize },
    /// A column name appears twice in the header.
    DuplicateColumn(String),
    /// A requested column is not in the header.
    MissingColumn(String),
    /// A data row does not have as many fields as the header.
    FieldCount { line: usize, expected: usize, found: usize },
    /// An amount field is not a valid amount.
    BadAmount { line: usize, text: String },
    /// A group's sum does not fit in i64 cents.
    Overflow { group: String },
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Empty => write!(f, "no header line"),
            Error::UnterminatedQuote { line } => write!(f, "line {line}: unterminated quote"),
            Error::BadQuote { line } => write!(f, "line {line}: misplaced quote"),
            Error::DuplicateColumn(name) => write!(f, "duplicate column {name:?}"),
            Error::MissingColumn(name) => write!(f, "missing column {name:?}"),
            Error::FieldCount { line, expected, found } => {
                write!(f, "line {line}: expected {expected} fields, found {found}")
            }
            Error::BadAmount { line, text } => write!(f, "line {line}: bad amount {text:?}"),
            Error::Overflow { group } => write!(f, "sum overflows for group {group:?}"),
        }
    }
}

impl std::error::Error for Error {}
