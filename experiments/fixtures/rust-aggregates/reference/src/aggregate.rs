use std::collections::BTreeMap;

use crate::error::Error;
use crate::parser::Table;

/// Totals for one group. Money values are in cents.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Summary {
    pub key: String,
    pub rows: usize,
    pub values: usize,
    pub sum: i64,
    pub min: Option<i64>,
    pub max: Option<i64>,
    pub mean: Option<i64>,
}

impl Summary {
    fn new(key: &str) -> Self {
        Summary { key: key.to_string(), rows: 0, values: 0, sum: 0, min: None, max: None, mean: None }
    }
}

/// Parses an amount such as `-12.5` into cents. An empty field is no value.
pub fn parse_cents(text: &str, line: usize) -> Result<Option<i64>, Error> {
    if text.is_empty() {
        return Ok(None);
    }
    let bad = || Error::BadAmount { line, text: text.to_string() };
    let (negative, body) = match text.strip_prefix('-') {
        Some(rest) => (true, rest),
        None => (false, text),
    };
    let (whole, frac) = match body.split_once('.') {
        Some((w, f)) => (w, Some(f)),
        None => (body, None),
    };
    if whole.is_empty() || !whole.bytes().all(|b| b.is_ascii_digit()) {
        return Err(bad());
    }
    let frac_cents: i128 = match frac {
        None => 0,
        Some(f) if (f.len() == 1 || f.len() == 2) && f.bytes().all(|b| b.is_ascii_digit()) => {
            let v: i128 = f.parse().map_err(|_| bad())?;
            if f.len() == 1 {
                v * 10
            } else {
                v
            }
        }
        Some(_) => return Err(bad()),
    };
    let limit = i64::MAX as i128 / 100 + 1;
    let mut units: i128 = 0;
    for b in whole.bytes() {
        units = units * 10 + i128::from(b - b'0');
        if units > limit {
            return Err(bad());
        }
    }
    let cents = units * 100 + frac_cents;
    let cents = if negative { -cents } else { cents };
    i64::try_from(cents).map(Some).map_err(|_| bad())
}

/// Mean of `count` values summing to `sum`, rounded half away from zero.
fn rounded_mean(sum: i64, count: usize) -> i64 {
    let s = i128::from(sum);
    let n = count as i128;
    let (q, r) = (s / n, s % n);
    let adjust = if 2 * r.abs() >= n { s.signum() } else { 0 };
    (q + adjust) as i64
}

fn column(names: &[String], name: &str) -> Result<usize, Error> {
    names.iter().position(|n| n == name).ok_or_else(|| Error::MissingColumn(name.to_string()))
}

/// Groups the rows by `group_col` and totals `value_col`, sorted by key.
pub fn aggregate(table: &Table, group_col: &str, value_col: &str) -> Result<Vec<Summary>, Error> {
    let g = column(&table.header, group_col)?;
    let v = column(&table.header, value_col)?;
    let mut groups: BTreeMap<String, Summary> = BTreeMap::new();
    for row in &table.rows {
        let key = &row.fields[g];
        let amount = parse_cents(&row.fields[v], row.line)?;
        let s = groups.entry(key.clone()).or_insert_with(|| Summary::new(key));
        s.rows += 1;
        if let Some(c) = amount {
            s.values += 1;
            s.sum = s.sum.checked_add(c).ok_or_else(|| Error::Overflow { group: key.clone() })?;
            s.min = Some(s.min.map_or(c, |m| m.min(c)));
            s.max = Some(s.max.map_or(c, |m| m.max(c)));
        }
    }
    let mut out: Vec<Summary> = groups.into_values().collect();
    for s in &mut out {
        if s.values > 0 {
            s.mean = Some(rounded_mean(s.sum, s.values));
        }
    }
    Ok(out)
}
