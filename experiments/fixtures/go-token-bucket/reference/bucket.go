// Package bucket implements a token-bucket rate limiter on an injected clock.
package bucket

import (
	"errors"
	"fmt"
	"math"
	"time"
)

var (
	ErrInvalidConfig   = errors.New("bucket: invalid config")
	ErrInvalidN        = errors.New("bucket: n must be positive")
	ErrExceedsCapacity = errors.New("bucket: n exceeds capacity")
)

// Limiter is a token bucket. The balance may be fractional, and negative after Reserve.
type Limiter struct {
	capacity float64
	rate     float64
	tokens   float64
	last     time.Time
	now      func() time.Time
}

// New returns a full limiter holding up to capacity tokens, refilled at ratePerSecond.
func New(capacity int, ratePerSecond float64, now func() time.Time) (*Limiter, error) {
	if capacity < 1 {
		return nil, fmt.Errorf("%w: capacity %d < 1", ErrInvalidConfig, capacity)
	}
	if !(ratePerSecond > 0) || math.IsInf(ratePerSecond, 1) {
		return nil, fmt.Errorf("%w: rate %v", ErrInvalidConfig, ratePerSecond)
	}
	if now == nil {
		return nil, fmt.Errorf("%w: nil clock", ErrInvalidConfig)
	}
	return &Limiter{capacity: float64(capacity), rate: ratePerSecond, tokens: float64(capacity), last: now(), now: now}, nil
}

// refill credits the time elapsed since the last observed time. A clock that went
// backwards credits nothing and does not move the last observed time.
func (l *Limiter) refill() {
	t := l.now()
	if t.Before(l.last) {
		return
	}
	l.tokens = math.Min(l.capacity, l.tokens+t.Sub(l.last).Seconds()*l.rate)
	l.last = t
}

// Allow takes n tokens if they are all available now.
func (l *Limiter) Allow(n int) bool {
	l.refill()
	switch {
	case n == 0:
		return true
	case n < 0 || float64(n) > l.capacity:
		return false
	case l.tokens < float64(n):
		return false
	}
	l.tokens -= float64(n)
	return true
}

// Reserve takes n tokens now, going into debt if needed, and returns how long to wait.
func (l *Limiter) Reserve(n int) (time.Duration, error) {
	l.refill()
	if n <= 0 {
		return 0, fmt.Errorf("%w: %d", ErrInvalidN, n)
	}
	if float64(n) > l.capacity {
		return 0, fmt.Errorf("%w: %d > %v", ErrExceedsCapacity, n, l.capacity)
	}
	before := l.tokens
	l.tokens -= float64(n)
	if before >= float64(n) {
		return 0, nil
	}
	shortfall := float64(n) - before
	return time.Duration(math.Ceil(shortfall / l.rate * float64(time.Second))), nil
}

// Tokens returns the current balance after refilling.
func (l *Limiter) Tokens() float64 {
	l.refill()
	return l.tokens
}
