package kvstore

// Begin opens a transaction nested inside the current one, if any.
func (s *Store) Begin() {
	s.txs = append(s.txs, make(map[string]change))
}

// Depth returns the number of open transactions.
func (s *Store) Depth() int {
	return len(s.txs)
}

// Rollback discards the innermost transaction.
func (s *Store) Rollback() error {
	n := len(s.txs)
	if n == 0 {
		return ErrNoTransaction
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
	for key, c := range top {
		if c.deleted {
			// The key is gone, so drop it from the level below as well.
			if n > 1 {
				delete(s.txs[n-2], key)
			} else {
				delete(s.data, key)
			}
			continue
		}
		s.put(key, c)
	}
	return nil
}
