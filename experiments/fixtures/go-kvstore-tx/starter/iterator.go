package kvstore

import "sort"

// Iterator walks keys in ascending byte-wise order.
type Iterator struct {
	store *Store
	keys  []string
	pos   int
}

// Iter returns an iterator over every visible key.
func (s *Store) Iter() *Iterator {
	return s.Range("", "")
}

// Range returns an iterator over the keys k with lo <= k < hi; an empty hi
// means there is no upper bound.
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
	return &Iterator{store: s, keys: keys, pos: -1}
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
	if it.pos < 0 || it.pos >= len(it.keys) {
		return ""
	}
	v, _ := it.store.Get(it.keys[it.pos])
	return v
}
