package kvstore

import (
	"errors"
	"reflect"
	"testing"
)

func hcollect(it *Iterator) []string {
	out := []string{}
	for it.Next() {
		out = append(out, it.Key()+"="+it.Value())
	}
	return out
}

func wantGet(t *testing.T, s *Store, key, value string, found bool) {
	t.Helper()
	v, ok := s.Get(key)
	if v != value || ok != found {
		t.Fatalf("Get(%q) = %q, %v; want %q, %v", key, v, ok, value, found)
	}
}

func wantCount(t *testing.T, s *Store, value string, n int) {
	t.Helper()
	if got := s.Count(value); got != n {
		t.Fatalf("Count(%q) = %d; want %d", value, got, n)
	}
}

func wantLen(t *testing.T, s *Store, n int) {
	t.Helper()
	if got := s.Len(); got != n {
		t.Fatalf("Len() = %d; want %d", got, n)
	}
}

func wantIter(t *testing.T, it *Iterator, want ...string) {
	t.Helper()
	if want == nil {
		want = []string{}
	}
	if got := hcollect(it); !reflect.DeepEqual(got, want) {
		t.Fatalf("iterator yielded %v; want %v", got, want)
	}
}

func mustOK(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

// R1
func TestHiddenNewStoreIsEmpty(t *testing.T) {
	s := New()
	wantGet(t, s, "x", "", false)
	wantCount(t, s, "", 0)
	wantCount(t, s, "a", 0)
	wantLen(t, s, 0)
	if s.Depth() != 0 {
		t.Fatalf("Depth() = %d; want 0", s.Depth())
	}
}

// R2
func TestHiddenSetGetOverwriteEmpty(t *testing.T) {
	s := New()
	s.Set("a", "1")
	wantGet(t, s, "a", "1", true)
	s.Set("a", "2")
	wantGet(t, s, "a", "2", true)
	s.Set("k", "")
	wantGet(t, s, "k", "", true)
	s.Set("", "empty key")
	wantGet(t, s, "", "empty key", true)
}

// R3
func TestHiddenDelete(t *testing.T) {
	s := New()
	s.Set("a", "1")
	s.Set("b", "1")
	s.Delete("a")
	wantGet(t, s, "a", "", false)
	s.Delete("a")
	s.Delete("missing")
	wantLen(t, s, 1)
	wantCount(t, s, "1", 1)
	wantCount(t, s, "", 0)
}

// R4
func TestHiddenLen(t *testing.T) {
	s := New()
	s.Set("a", "x")
	s.Set("b", "y")
	s.Set("c", "z")
	wantLen(t, s, 3)
	s.Set("a", "w")
	wantLen(t, s, 3)
	s.Delete("b")
	s.Delete("b")
	wantLen(t, s, 2)
}

// R5
func TestHiddenCount(t *testing.T) {
	s := New()
	s.Set("a", "x")
	s.Set("b", "x")
	s.Set("c", "y")
	s.Set("d", "")
	wantCount(t, s, "x", 2)
	wantCount(t, s, "y", 1)
	wantCount(t, s, "z", 0)
	wantCount(t, s, "", 1)
}

// R6
func TestHiddenCountThroughOverwrites(t *testing.T) {
	s := New()
	s.Set("a", "x")
	s.Set("b", "y")
	s.Set("a", "y")
	wantCount(t, s, "x", 0)
	wantCount(t, s, "y", 2)
	s.Set("a", "y")
	wantCount(t, s, "y", 2)
	wantLen(t, s, 2)
	s.Delete("a")
	wantCount(t, s, "y", 1)
	wantLen(t, s, 1)
}

// R7
func TestHiddenDepth(t *testing.T) {
	s := New()
	s.Begin()
	s.Begin()
	if s.Depth() != 2 {
		t.Fatalf("Depth() = %d; want 2", s.Depth())
	}
	mustOK(t, s.Commit())
	if s.Depth() != 1 {
		t.Fatalf("Depth() after Commit = %d; want 1", s.Depth())
	}
	mustOK(t, s.Rollback())
	if s.Depth() != 0 {
		t.Fatalf("Depth() after Rollback = %d; want 0", s.Depth())
	}
}

// R8
func TestHiddenViewThroughLayers(t *testing.T) {
	s := New()
	s.Set("a", "1")
	s.Begin()
	s.Set("a", "2")
	wantGet(t, s, "a", "2", true)
	s.Begin()
	s.Set("b", "3")
	wantGet(t, s, "a", "2", true)
	wantGet(t, s, "b", "3", true)
	wantCount(t, s, "2", 1)
	wantCount(t, s, "1", 0)
	wantLen(t, s, 2)
	wantIter(t, s.Iter(), "a=2", "b=3")
}

// R9
func TestHiddenDeleteHidesLowerValues(t *testing.T) {
	s := New()
	s.Set("a", "1")
	s.Begin()
	s.Delete("a")
	wantGet(t, s, "a", "", false)
	wantLen(t, s, 0)
	s.Begin()
	s.Set("a", "5")
	wantGet(t, s, "a", "5", true)
	mustOK(t, s.Rollback())
	wantGet(t, s, "a", "", false)
	s.Set("a", "7")
	wantGet(t, s, "a", "7", true)
	mustOK(t, s.Rollback())
	wantGet(t, s, "a", "1", true)
}

// R10
func TestHiddenRollbackOnlyInnermost(t *testing.T) {
	s := New()
	s.Set("a", "1")
	s.Begin()
	s.Set("a", "2")
	s.Set("b", "2")
	s.Begin()
	s.Set("a", "3")
	s.Delete("b")
	mustOK(t, s.Rollback())
	wantGet(t, s, "a", "2", true)
	wantGet(t, s, "b", "2", true)
	mustOK(t, s.Rollback())
	wantGet(t, s, "a", "1", true)
	wantGet(t, s, "b", "", false)
}

// R11
func TestHiddenCommitMergesIntoParent(t *testing.T) {
	s := New()
	s.Begin()
	s.Set("a", "1")
	s.Begin()
	s.Set("b", "2")
	mustOK(t, s.Commit())
	wantGet(t, s, "a", "1", true)
	wantGet(t, s, "b", "2", true)
	mustOK(t, s.Rollback())
	wantGet(t, s, "a", "", false)
	wantGet(t, s, "b", "", false)
	wantLen(t, s, 0)

	s.Begin()
	s.Set("c", "3")
	mustOK(t, s.Commit())
	if err := s.Rollback(); !errors.Is(err, ErrNoTransaction) {
		t.Fatalf("Rollback with no transaction = %v; want ErrNoTransaction", err)
	}
	wantGet(t, s, "c", "3", true)
}

// R12
func TestHiddenCommittedDeleteStaysHidden(t *testing.T) {
	s := New()
	s.Set("a", "1")
	s.Set("keep", "k")
	s.Begin()
	s.Begin()
	s.Delete("a")
	mustOK(t, s.Commit())
	wantGet(t, s, "a", "", false)
	wantLen(t, s, 1)
	wantCount(t, s, "1", 0)
	wantIter(t, s.Iter(), "keep=k")
	mustOK(t, s.Commit())
	wantGet(t, s, "a", "", false)
	wantLen(t, s, 1)
	wantIter(t, s.Iter(), "keep=k")
}

// R12
func TestHiddenCommittedDeleteOverridesParentValue(t *testing.T) {
	s := New()
	s.Set("a", "1")
	s.Begin()
	s.Set("a", "2")
	s.Begin()
	s.Delete("a")
	mustOK(t, s.Commit())
	wantGet(t, s, "a", "", false)
	wantCount(t, s, "2", 0)
	wantCount(t, s, "1", 0)
	mustOK(t, s.Rollback())
	wantGet(t, s, "a", "1", true)
	wantCount(t, s, "1", 1)
}

// R13
func TestHiddenCountsAfterNestedRollback(t *testing.T) {
	s := New()
	s.Set("a", "1")
	s.Begin()
	s.Set("a", "2")
	s.Begin()
	s.Set("a", "3")
	wantCount(t, s, "3", 1)
	wantCount(t, s, "2", 0)
	mustOK(t, s.Rollback())
	wantCount(t, s, "2", 1)
	wantCount(t, s, "3", 0)
	wantCount(t, s, "1", 0)
	wantLen(t, s, 1)
	mustOK(t, s.Rollback())
	wantCount(t, s, "1", 1)
	wantCount(t, s, "2", 0)
	wantLen(t, s, 1)
}

// R13
func TestHiddenCountsAfterRollingBackDeletes(t *testing.T) {
	s := New()
	s.Set("a", "1")
	s.Set("b", "1")
	s.Begin()
	s.Delete("a")
	wantCount(t, s, "1", 1)
	wantLen(t, s, 1)
	mustOK(t, s.Rollback())
	wantCount(t, s, "1", 2)
	wantCount(t, s, "", 0)
	wantLen(t, s, 2)

	s.Begin()
	s.Delete("a")
	s.Begin()
	s.Set("a", "4")
	wantCount(t, s, "4", 1)
	mustOK(t, s.Rollback())
	wantCount(t, s, "4", 0)
	wantCount(t, s, "1", 1)
	wantLen(t, s, 1)
	mustOK(t, s.Rollback())
	wantCount(t, s, "1", 2)
	wantLen(t, s, 2)
}

// R13
func TestHiddenCountsForNewKeysEmptyValuesAndCommit(t *testing.T) {
	s := New()
	s.Begin()
	s.Set("n", "9")
	s.Set("e", "")
	wantCount(t, s, "", 1)
	mustOK(t, s.Rollback())
	wantCount(t, s, "9", 0)
	wantCount(t, s, "", 0)
	wantLen(t, s, 0)

	s.Set("a", "1")
	s.Begin()
	s.Set("a", "2")
	s.Begin()
	s.Set("b", "2")
	mustOK(t, s.Commit())
	wantCount(t, s, "2", 2)
	mustOK(t, s.Commit())
	wantCount(t, s, "2", 2)
	wantCount(t, s, "1", 0)
	wantLen(t, s, 2)
}

// R14
func TestHiddenNoTransactionErrors(t *testing.T) {
	s := New()
	s.Set("a", "1")
	if err := s.Commit(); !errors.Is(err, ErrNoTransaction) {
		t.Fatalf("Commit() = %v; want ErrNoTransaction", err)
	}
	if err := s.Rollback(); !errors.Is(err, ErrNoTransaction) {
		t.Fatalf("Rollback() = %v; want ErrNoTransaction", err)
	}
	wantGet(t, s, "a", "1", true)
	wantLen(t, s, 1)
	if s.Depth() != 0 {
		t.Fatalf("Depth() = %d; want 0", s.Depth())
	}
	s.Begin()
	if err := s.Commit(); err != nil {
		t.Fatalf("Commit() with a transaction = %v; want nil", err)
	}
	s.Begin()
	if err := s.Rollback(); err != nil {
		t.Fatalf("Rollback() with a transaction = %v; want nil", err)
	}
}

// R15
func TestHiddenIterOrderAndRange(t *testing.T) {
	s := New()
	for _, k := range []string{"b", "a", "ba", "ab", "c", "Z", "B", "é", ""} {
		s.Set(k, "v"+k)
	}
	wantIter(t, s.Iter(), "=v", "B=vB", "Z=vZ", "a=va", "ab=vab", "b=vb", "ba=vba", "c=vc", "é=vé")
	wantIter(t, s.Range("ab", "ba"), "ab=vab", "b=vb")
	wantIter(t, s.Range("b", ""), "b=vb", "ba=vba", "c=vc", "é=vé")
	wantIter(t, s.Range("", "B"), "=v")
	wantIter(t, s.Range("x", "y"))
}

// R16
func TestHiddenIteratorProtocol(t *testing.T) {
	s := New()
	s.Set("a", "1")
	it := s.Iter()
	if !it.Next() || it.Key() != "a" || it.Value() != "1" {
		t.Fatalf("first entry = %q=%q; want a=1", it.Key(), it.Value())
	}
	for i := 0; i < 3; i++ {
		if it.Next() {
			t.Fatal("Next() returned true after the last entry")
		}
	}
	if New().Iter().Next() {
		t.Fatal("Next() on an empty store returned true")
	}
}

// R17
func TestHiddenIteratorIsSnapshot(t *testing.T) {
	s := New()
	s.Set("a", "1")
	s.Set("b", "2")
	s.Set("c", "3")
	it := s.Iter()
	r := s.Range("b", "")
	s.Set("b", "20")
	s.Delete("c")
	s.Set("d", "4")
	s.Begin()
	s.Set("a", "100")
	s.Delete("b")
	wantIter(t, it, "a=1", "b=2", "c=3")
	mustOK(t, s.Rollback())
	wantIter(t, r, "b=2", "c=3")
}

// R17
func TestHiddenIteratorSnapshotDuringIteration(t *testing.T) {
	s := New()
	s.Set("a", "1")
	s.Set("b", "2")
	it := s.Iter()
	if !it.Next() || it.Key() != "a" {
		t.Fatal("expected a first")
	}
	s.Set("b", "changed")
	s.Set("aa", "new")
	if !it.Next() || it.Key() != "b" || it.Value() != "2" {
		t.Fatalf("second entry = %q=%q; want b=2", it.Key(), it.Value())
	}
	if it.Next() {
		t.Fatal("iterator yielded a key added after it was created")
	}
}

// R18
func TestHiddenIteratorInsideTransaction(t *testing.T) {
	s := New()
	s.Set("a", "1")
	s.Set("b", "2")
	s.Begin()
	s.Set("c", "3")
	s.Begin()
	s.Delete("a")
	s.Set("d", "4")
	it := s.Iter()
	committed := s.Range("", "")
	mustOK(t, s.Rollback())
	wantIter(t, it, "b=2", "c=3", "d=4")
	mustOK(t, s.Commit())
	wantIter(t, committed, "b=2", "c=3", "d=4")
	wantIter(t, s.Iter(), "a=1", "b=2", "c=3")
}

// R19
func TestHiddenManyIterators(t *testing.T) {
	s := New()
	s.Set("a", "1")
	first := s.Iter()
	s.Set("b", "2")
	second := s.Iter()
	s.Delete("a")
	third := s.Iter()
	if !second.Next() || second.Key() != "a" {
		t.Fatal("second iterator should start at a")
	}
	wantIter(t, first, "a=1")
	if !second.Next() || second.Key() != "b" || second.Value() != "2" {
		t.Fatal("second iterator should continue with b=2")
	}
	wantIter(t, third, "b=2")
}
