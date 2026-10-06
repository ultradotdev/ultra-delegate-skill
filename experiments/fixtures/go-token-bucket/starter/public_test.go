package bucket

import (
	"testing"
	"time"
)

type publicClock struct{ t time.Time }

func (c *publicClock) now() time.Time          { return c.t }
func (c *publicClock) advance(d time.Duration) { c.t = c.t.Add(d) }

func newPublic(t *testing.T, capacity int, rate float64) (*Limiter, *publicClock) {
	t.Helper()
	c := &publicClock{t: time.Unix(1_700_000_000, 0)}
	l, err := New(capacity, rate, c.now)
	if err != nil {
		t.Fatalf("New(%d, %v): %v", capacity, rate, err)
	}
	return l, c
}

func TestPublicStartsFullAndConsumes(t *testing.T) {
	l, _ := newPublic(t, 3, 1)
	steps := []struct {
		n    int
		want bool
	}{{2, true}, {2, false}, {1, true}, {1, false}}
	for i, s := range steps {
		if got := l.Allow(s.n); got != s.want {
			t.Fatalf("step %d: Allow(%d) = %v, want %v", i, s.n, got, s.want)
		}
	}
}

func TestPublicRefill(t *testing.T) {
	l, c := newPublic(t, 5, 2)
	if !l.Allow(5) {
		t.Fatal("Allow(5) on a full bucket should succeed")
	}
	c.advance(time.Second)
	if !l.Allow(2) {
		t.Fatal("after 1s at 2/s, Allow(2) should succeed")
	}
	if l.Allow(1) {
		t.Fatal("bucket should be empty again")
	}
}

func TestPublicBurstIsCapped(t *testing.T) {
	l, c := newPublic(t, 3, 1)
	c.advance(time.Hour)
	if l.Allow(4) {
		t.Fatal("Allow(4) must fail when capacity is 3")
	}
	if !l.Allow(3) {
		t.Fatal("Allow(3) should succeed after idling")
	}
	if l.Allow(1) {
		t.Fatal("idle time must not bank more than capacity")
	}
}
