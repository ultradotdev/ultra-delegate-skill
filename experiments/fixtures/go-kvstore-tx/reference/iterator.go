package kvstore

import "sort"

// Iterator walks a snapshot of entries in ascending byte-wise key order.
type Iterator struct {
	keys   []string
	values []string
	pos    int
}

// Iter returns an iterator over every visible key.
func (s *Store) Iter() *Iterator {
	return s.Range("", "")
}

// Range returns an iterator over the keys k with lo <= k < hi; an empty hi
// means there is no upper bound. Keys and values are copied now, so later
// writes do not affect the iterator.
func (s *Store) Range(lo, hi string) *Iterator {
	seen := make(map[string]bool)
	var keys []string
	add := func(k string) {
		if seen[k] || k < lo || (hi != "" && k >= hi) {
			return
		}
		seen[k] = true
		keys = append(keys, k)
	}
	for k := range s.data {
		add(k)
	}
	for _, tx := range s.txs {
		for k := range tx {
			add(k)
		}
	}
	sort.Strings(keys)
	it := &Iterator{pos: -1}
	for _, k := range keys {
		if v, ok := s.Get(k); ok {
			it.keys = append(it.keys, k)
			it.values = append(it.values, v)
		}
	}
	return it
}

// Next advances to the next entry and reports whether there is one.
func (it *Iterator) Next() bool {
	if it.pos < len(it.keys) {
		it.pos++
	}
	return it.pos < len(it.keys)
}

// Key returns the current entry's key.
func (it *Iterator) Key() string {
	if it.pos < 0 || it.pos >= len(it.keys) {
		return ""
	}
	return it.keys[it.pos]
}

// Value returns the current entry's value.
func (it *Iterator) Value() string {
	if it.pos < 0 || it.pos >= len(it.values) {
		return ""
	}
	return it.values[it.pos]
}
