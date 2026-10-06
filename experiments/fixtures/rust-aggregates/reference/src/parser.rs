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

/// Splits one line into fields. Unquoted fields are trimmed of spaces; quoted
/// fields keep their content exactly, with `""` standing for `"`.
pub fn parse_line(text: &str, line: usize) -> Result<Vec<String>, Error> {
    let chars: Vec<char> = text.chars().collect();
    let mut fields = Vec::new();
    let mut i = 0;
    loop {
        while i < chars.len() && chars[i] == ' ' {
            i += 1;
        }
        if i < chars.len() && chars[i] == '"' {
            i += 1;
            let mut content = String::new();
            loop {
                if i >= chars.len() {
                    return Err(Error::UnterminatedQuote { line });
                }
                if chars[i] == '"' {
                    if i + 1 < chars.len() && chars[i + 1] == '"' {
                        content.push('"');
                        i += 2;
                        continue;
                    }
                    i += 1;
                    break;
                }
                content.push(chars[i]);
                i += 1;
            }
            while i < chars.len() && chars[i] == ' ' {
                i += 1;
            }
            fields.push(content);
            if i >= chars.len() {
                break;
            }
            if chars[i] != ',' {
                return Err(Error::BadQuote { line });
            }
            i += 1;
        } else {
            let start = i;
            while i < chars.len() && chars[i] != ',' {
                if chars[i] == '"' {
                    return Err(Error::BadQuote { line });
                }
                i += 1;
            }
            let field: String = chars[start..i].iter().collect();
            fields.push(field.trim_end_matches(' ').to_string());
            if i >= chars.len() {
                break;
            }
            i += 1;
        }
    }
    Ok(fields)
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
