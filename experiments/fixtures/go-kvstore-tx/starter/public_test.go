package kvstore

import (
	"reflect"
	"testing"
)

func publicCollect(it *Iterator) []string {
	var out []string
	for it.Next() {
		out = append(out, it.Key()+"="+it.Value())
	}
	return out
}

func TestPublicBasics(t *testing.T) {
	s := New()
	s.Set("a", "10")
	s.Set("b", "10")
	s.Set("c", "20")
	if v, ok := s.Get("a"); !ok || v != "10" {
		t.Fatalf(`Get("a") = %q, %v; want "10", true`, v, ok)
	}
	if got := s.Count("10"); got != 2 {
		t.Fatalf(`Count("10") = %d; want 2`, got)
	}
	s.Delete("a")
	if _, ok := s.Get("a"); ok {
		t.Fatal(`Get("a") found a deleted key`)
	}
	if got := s.Count("10"); got != 1 {
		t.Fatalf(`Count("10") after delete = %d; want 1`, got)
	}
}

func TestPublicRollback(t *testing.T) {
	s := New()
	s.Set("a", "10")
	s.Begin()
	s.Set("a", "20")
	s.Set("b", "20")
	if got := s.Count("20"); got != 2 {
		t.Fatalf(`Count("20") inside transaction = %d; want 2`, got)
	}
	if err := s.Rollback(); err != nil {
		t.Fatalf("Rollback: %v", err)
	}
	if v, _ := s.Get("a"); v != "10" {
		t.Fatalf(`Get("a") after rollback = %q; want "10"`, v)
	}
	if got := s.Count("20"); got != 0 {
		t.Fatalf(`Count("20") after rollback = %d; want 0`, got)
	}
	if got := s.Count("10"); got != 1 {
		t.Fatalf(`Count("10") after rollback = %d; want 1`, got)
	}
	if got := s.Len(); got != 1 {
		t.Fatalf("Len() after rollback = %d; want 1", got)
	}
}

func TestPublicCommit(t *testing.T) {
	s := New()
	s.Begin()
	s.Set("a", "1")
	if err := s.Commit(); err != nil {
		t.Fatalf("Commit: %v", err)
	}
	if v, ok := s.Get("a"); !ok || v != "1" || s.Depth() != 0 {
		t.Fatalf(`after commit: Get("a") = %q, %v; Depth() = %d`, v, ok, s.Depth())
	}
}

func TestPublicIter(t *testing.T) {
	s := New()
	for _, k := range []string{"pear", "apple", "fig"} {
		s.Set(k, k+"!")
	}
	want := []string{"apple=apple!", "fig=fig!", "pear=pear!"}
	if got := publicCollect(s.Iter()); !reflect.DeepEqual(got, want) {
		t.Fatalf("Iter() = %v; want %v", got, want)
	}
}
