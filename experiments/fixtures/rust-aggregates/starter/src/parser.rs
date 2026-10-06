use crate::error::Error;

/// One data row and the physical line it came from.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Row {
    pub line: usize,
    pub fields: Vec<String>,
}

/// The header and the data rows of an input.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Table {
    pub header: Vec<String>,
    pub rows: Vec<Row>,
}

/// Splits one line into fields. Fields are trimmed of spaces; quoted fields
/// may contain `""` for a literal quote.
pub fn parse_line(text: &str, line: usize) -> Result<Vec<String>, Error> {
    text.split(',').map(|raw| parse_field(raw, line)).collect()
}

fn parse_field(raw: &str, line: usize) -> Result<String, Error> {
    let field = raw.trim_matches(' ');
    if let Some(rest) = field.strip_prefix('"') {
        let inner = rest.strip_suffix('"').ok_or(Error::UnterminatedQuote { line })?;
        if inner.replace("\"\"", "").contains('"') {
            return Err(Error::BadQuote { line });
        }
        return Ok(inner.replace("\"\"", "\"").trim_matches(' ').to_string());
    }
    if field.contains('"') {
        return Err(Error::BadQuote { line });
    }
    Ok(field.to_string())
}

/// Reads the header and data rows, skipping blank lines but numbering every
/// physical line.
pub fn parse_table(input: &str) -> Result<Table, Error> {
    let mut header: Option<Vec<String>> = None;
    let mut rows = Vec::new();
    for (index, raw) in input.split('\n').enumerate() {
        let line = index + 1;
        let text = raw.strip_suffix('\r').unwrap_or(raw);
        if text.trim_matches(' ').is_empty() {
            continue;
        }
        let fields = parse_line(text, line)?;
        match &header {
            None => {
                for (i, name) in fields.iter().enumerate() {
                    if fields[..i].contains(name) {
                        return Err(Error::DuplicateColumn(name.clone()));
                    }
                }
                header = Some(fields);
            }
            Some(names) => {
                if fields.len() != names.len() {
                    return Err(Error::FieldCount { line, expected: names.len(), found: fields.len() });
                }
                rows.push(Row { line, fields });
            }
        }
    }
    let header = header.ok_or(Error::Empty)?;
    Ok(Table { header, rows })
}
