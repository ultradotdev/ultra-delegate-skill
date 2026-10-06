// Package kvstore is an in-memory key-value store with nested transactions.
package kvstore

import "errors"

// ErrNoTransaction is returned by Commit and Rollback when no transaction is open.
var ErrNoTransaction = errors.New("kvstore: no open transaction")

// change is one key's pending change inside a transaction.
type change struct {
	value   string
	deleted bool
}

// Store holds the committed data plus a stack of open transactions.
type Store struct {
	data   map[string]string   // committed data
	txs    []map[string]change // open transactions, innermost last
	counts map[string]int      // visible value -> number of visible keys holding it
	size   int                 // number of visible keys
}

// New returns an empty store.
func New() *Store {
	return &Store{data: make(map[string]string), counts: make(map[string]int)}
}

// Get returns the visible value of key.
func (s *Store) Get(key string) (string, bool) {
	for i := len(s.txs) - 1; i >= 0; i-- {
		if c, ok := s.txs[i][key]; ok {
			if c.deleted {
				return "", false
			}
			return c.value, true
		}
	}
	v, ok := s.data[key]
	return v, ok
}

// Set makes key visible with value.
func (s *Store) Set(key, value string) {
	old, had := s.Get(key)
	s.track(old, had, value, true)
	s.put(key, change{value: value})
}

// Delete hides key. Deleting a key that is not visible does nothing.
func (s *Store) Delete(key string) {
	old, had := s.Get(key)
	if !had {
		return
	}
	s.track(old, true, "", false)
	s.put(key, change{deleted: true})
}

// Count returns the number of visible keys whose value is value.
func (s *Store) Count(value string) int {
	return s.counts[value]
}

// Len returns the number of visible keys.
func (s *Store) Len() int {
	return s.size
}

// track moves one key's contribution to counts and size from its old visible
// state (oldValue, hadOld) to its new one (newValue, hasNew).
func (s *Store) track(oldValue string, hadOld bool, newValue string, hasNew bool) {
	if hadOld {
		s.counts[oldValue]--
		if s.counts[oldValue] == 0 {
			delete(s.counts, oldValue)
		}
		s.size--
	}
	if hasNew {
		s.counts[newValue]++
		s.size++
	}
}

// put records a change in the innermost transaction, or applies it to the
// committed data when no transaction is open.
func (s *Store) put(key string, c change) {
	if n := len(s.txs); n > 0 {
		s.txs[n-1][key] = c
		return
	}
	if c.deleted {
		delete(s.data, key)
	} else {
		s.data[key] = c.value
	}
}
