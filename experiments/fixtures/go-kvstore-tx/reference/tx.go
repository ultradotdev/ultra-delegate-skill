package kvstore

// Begin opens a transaction nested inside the current one, if any.
func (s *Store) Begin() {
	s.txs = append(s.txs, make(map[string]change))
}

// Depth returns the number of open transactions.
func (s *Store) Depth() int {
	return len(s.txs)
}

// visibleAt returns key's value as seen through the outermost depth
// transactions and the committed data (depth 0 means the committed data only).
func (s *Store) visibleAt(key string, depth int) (string, bool) {
	for i := depth - 1; i >= 0; i-- {
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

// Rollback discards the innermost transaction.
func (s *Store) Rollback() error {
	n := len(s.txs)
	if n == 0 {
		return ErrNoTransaction
	}
	// Every key the transaction touched goes back to what the enclosing view shows.
	for key := range s.txs[n-1] {
		cur, hadCur := s.visibleAt(key, n)
		prev, hadPrev := s.visibleAt(key, n-1)
		s.track(cur, hadCur, prev, hadPrev)
	}
	s.txs = s.txs[:n-1]
	return nil
}

// Commit merges the innermost transaction into the enclosing one, or into the
// committed data when it is the outermost.
func (s *Store) Commit() error {
	n := len(s.txs)
	if n == 0 {
		return ErrNoTransaction
	}
	top := s.txs[n-1]
	s.txs = s.txs[:n-1]
	// A delete stays a tombstone in the enclosing transaction (so it keeps hiding
	// values further down) and removes the key from the committed data. The view
	// does not change, so counts do not either.
	for key, c := range top {
		s.put(key, c)
	}
	return nil
}
