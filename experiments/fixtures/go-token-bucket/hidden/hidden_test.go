package bucket

import (
	"errors"
	"math"
	"testing"
	"time"
)

var hiddenEpoch = time.Unix(1_700_000_000, 0)

type hiddenClock struct{ t time.Time }

func (c *hiddenClock) now() time.Time { return c.t }

// at moves the clock to epoch + d (forwards or backwards).
func (c *hiddenClock) at(d time.Duration) { c.t = hiddenEpoch.Add(d) }

func newHidden(t *testing.T, capacity int, rate float64) (*Limiter, *hiddenClock) {
	t.Helper()
	c := &hiddenClock{t: hiddenEpoch}
	l, err := New(capacity, rate, c.now)
	if err != nil || l == nil {
		t.Fatalf("New(%d, %v) = %v, %v", capacity, rate, l, err)
	}
	return l, c
}

func wantTokens(t *testing.T, l *Limiter, want float64, label string) {
	t.Helper()
	if got := l.Tokens(); got != want {
		t.Fatalf("%s: Tokens() = %v, want %v", label, got, want)
	}
}

func wantAllow(t *testing.T, l *Limiter, n int, want bool, label string) {
	t.Helper()
	if got := l.Allow(n); got != want {
		t.Fatalf("%s: Allow(%d) = %v, want %v", label, n, got, want)
	}
}

func wantReserve(t *testing.T, l *Limiter, n int, want time.Duration, label string) {
	t.Helper()
	got, err := l.Reserve(n)
	if err != nil || got != want {
		t.Fatalf("%s: Reserve(%d) = %v, %v; want %v, nil", label, n, got, err, want)
	}
}

func TestHidden_R1_NewValidates(t *testing.T) {
	c := &hiddenClock{t: hiddenEpoch}
	cases := []struct {
		name     string
		capacity int
		rate     float64
		now      func() time.Time
	}{
		{"zero capacity", 0, 1, c.now},
		{"negative capacity", -1, 1, c.now},
		{"zero rate", 1, 0, c.now},
		{"negative rate", 1, -1, c.now},
		{"NaN rate", 1, math.NaN(), c.now},
		{"infinite rate", 1, math.Inf(1), c.now},
		{"nil clock", 1, 1, nil},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			defer func() {
				if r := recover(); r != nil {
					t.Fatalf("New panicked: %v", r)
				}
			}()
			l, err := New(tc.capacity, tc.rate, tc.now)
			if l != nil || !errors.Is(err, ErrInvalidConfig) {
				t.Fatalf("New = %v, %v; want nil, ErrInvalidConfig", l, err)
			}
		})
	}
	if l, err := New(1, 0.001, c.now); err != nil || l == nil {
		t.Fatalf("valid config rejected: %v", err)
	}
}

func TestHidden_R2_StartsFull(t *testing.T) {
	l, _ := newHidden(t, 7, 0.001)
	wantTokens(t, l, 7, "fresh")
	wantAllow(t, l, 7, true, "fresh")
	wantAllow(t, l, 1, false, "drained")
}

func TestHidden_R3_RefillOnEveryCall(t *testing.T) {
	l, c := newHidden(t, 2, 1)
	c.at(10 * time.Second)
	wantAllow(t, l, 2, true, "after idling while full")
	c.at(10*time.Second + 500*time.Millisecond)
	wantTokens(t, l, 0.5, "idle time while full must not count later")

	l, c = newHidden(t, 4, 1)
	wantAllow(t, l, 4, true, "drain")
	c.at(time.Second)
	wantAllow(t, l, 2, false, "failed call still refills")
	c.at(2 * time.Second)
	wantTokens(t, l, 2, "a failed call moves the last observed time")

	l, c = newHidden(t, 10, 2)
	wantAllow(t, l, 10, true, "drain")
	c.at(1500 * time.Millisecond)
	wantReserve(t, l, 3, 0, "reserve refills first")
	wantTokens(t, l, 0, "after reserve")
}

func TestHidden_R4_FractionalTokensAccumulate(t *testing.T) {
	l, c := newHidden(t, 1, 0.5)
	wantAllow(t, l, 1, true, "drain")
	c.at(time.Second)
	wantAllow(t, l, 1, false, "0.5 tokens")
	c.at(2 * time.Second)
	wantAllow(t, l, 1, true, "0.5 + 0.5 tokens")

	l, c = newHidden(t, 3, 3)
	wantAllow(t, l, 3, true, "drain")
	for i, want := range []float64{0.75, 1.5, 2.25, 3} {
		c.at(time.Duration(i+1) * 250 * time.Millisecond)
		wantTokens(t, l, want, "250ms steps at 3/s")
	}
}

func TestHidden_R5_ClockGoingBackwards(t *testing.T) {
	l, c := newHidden(t, 4, 1)
	wantAllow(t, l, 4, true, "drain")
	c.at(2 * time.Second)
	wantTokens(t, l, 2, "t=2s")
	c.at(time.Second)
	wantTokens(t, l, 2, "clock back to t=1s")
	c.at(2 * time.Second)
	wantTokens(t, l, 2, "forward to t=2s again: already counted")
	c.at(1500 * time.Millisecond)
	wantAllow(t, l, 2, true, "spending while the clock is behind")
	c.at(3 * time.Second)
	wantTokens(t, l, 1, "t=3s counts only from t=2s")

	l, c = newHidden(t, 2, 1)
	c.at(-time.Hour)
	wantTokens(t, l, 2, "clock before construction")
	c.at(0)
	wantAllow(t, l, 2, true, "back at construction time")
	c.at(-time.Minute)
	wantReserve(t, l, 1, time.Second, "reserve with clock behind")
}

func TestHidden_R6_AllowIsAllOrNothing(t *testing.T) {
	l, _ := newHidden(t, 5, 1)
	wantAllow(t, l, 3, true, "3 of 5")
	wantAllow(t, l, 3, false, "3 of 2")
	wantTokens(t, l, 2, "failed Allow consumes nothing")
	wantAllow(t, l, 2, true, "2 of 2")
	wantTokens(t, l, 0, "empty")

	l, c := newHidden(t, 2, 0.5)
	wantAllow(t, l, 2, true, "drain")
	c.at(time.Second)
	wantAllow(t, l, 1, false, "0.5 available")
	wantTokens(t, l, 0.5, "partial balance kept")
}

func TestHidden_R7_AllowEdgeArguments(t *testing.T) {
	l, _ := newHidden(t, 3, 1)
	wantAllow(t, l, 0, true, "zero on full bucket")
	wantTokens(t, l, 3, "zero consumes nothing")
	wantAllow(t, l, -1, false, "negative")
	wantAllow(t, l, 4, false, "above capacity on full bucket")
	wantTokens(t, l, 3, "rejected calls consume nothing")
	wantAllow(t, l, 3, true, "drain")
	wantAllow(t, l, 0, true, "zero on empty bucket")
	wantReserve(t, l, 3, 3*time.Second, "go into debt")
	wantAllow(t, l, 0, true, "zero while in debt")
}

func TestHidden_R8_ReserveRejectsBadN(t *testing.T) {
	l, _ := newHidden(t, 3, 1)
	for _, n := range []int{0, -2} {
		d, err := l.Reserve(n)
		if d != 0 || !errors.Is(err, ErrInvalidN) {
			t.Fatalf("Reserve(%d) = %v, %v; want 0, ErrInvalidN", n, d, err)
		}
	}
	d, err := l.Reserve(4)
	if d != 0 || !errors.Is(err, ErrExceedsCapacity) {
		t.Fatalf("Reserve(4) = %v, %v; want 0, ErrExceedsCapacity", d, err)
	}
	wantTokens(t, l, 3, "rejected reservations consume nothing")
}

func TestHidden_R9_ReserveTakesTokensAndReportsWait(t *testing.T) {
	l, _ := newHidden(t, 4, 2)
	wantReserve(t, l, 3, 0, "enough tokens")
	wantTokens(t, l, 1, "after first reserve")
	wantReserve(t, l, 3, time.Second, "shortfall of 2 at 2/s")
	wantTokens(t, l, -2, "debt")

	l, _ = newHidden(t, 2, 1)
	wantReserve(t, l, 2, 0, "exactly enough")
	wantTokens(t, l, 0, "exactly enough leaves zero")
}

func TestHidden_R10_WaitRoundsUp(t *testing.T) {
	l, _ := newHidden(t, 3, 3)
	wantAllow(t, l, 3, true, "drain")
	wantReserve(t, l, 1, 333333334*time.Nanosecond, "1 token at 3/s")

	l, _ = newHidden(t, 1, 7)
	wantAllow(t, l, 1, true, "drain")
	wantReserve(t, l, 1, 142857143*time.Nanosecond, "1 token at 7/s")

	l, _ = newHidden(t, 2, 4)
	wantAllow(t, l, 2, true, "drain")
	wantReserve(t, l, 1, 250*time.Millisecond, "exact waits are not bumped")
}

func TestHidden_R11_DebtRepaysAndQueues(t *testing.T) {
	l, c := newHidden(t, 2, 1)
	wantReserve(t, l, 2, 0, "first")
	wantReserve(t, l, 1, time.Second, "second")
	wantReserve(t, l, 2, 3*time.Second, "third waits for earlier debt")
	wantTokens(t, l, -3, "total debt")
	wantAllow(t, l, 1, false, "in debt")
	c.at(3 * time.Second)
	wantTokens(t, l, 0, "debt repaid")
	wantAllow(t, l, 1, false, "nothing spare yet")
	c.at(4 * time.Second)
	wantAllow(t, l, 1, true, "one token earned")
}

func TestHidden_R12_TokensReportsWithoutConsuming(t *testing.T) {
	l, c := newHidden(t, 3, 0.25)
	wantTokens(t, l, 3, "fresh")
	wantTokens(t, l, 3, "Tokens twice")
	wantAllow(t, l, 3, true, "drain")
	c.at(time.Second)
	wantTokens(t, l, 0.25, "fractional")
	wantTokens(t, l, 0.25, "fractional again")
	wantReserve(t, l, 1, 3*time.Second, "shortfall 0.75 at 0.25/s")
	wantTokens(t, l, -0.75, "negative")
}

func TestHidden_R13_BurstNeverExceedsCapacity(t *testing.T) {
	l, c := newHidden(t, 3, 4)
	c.at(time.Hour)
	wantTokens(t, l, 3, "after an hour idle")
	wantAllow(t, l, 3, true, "full burst")
	wantAllow(t, l, 1, false, "nothing beyond capacity")
	wantReserve(t, l, 3, 750*time.Millisecond, "into debt")
	c.at(2 * time.Hour)
	wantTokens(t, l, 3, "debt then long idle still caps")
}
