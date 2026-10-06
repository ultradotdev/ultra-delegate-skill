// Package bucket implements a token-bucket rate limiter on an injected clock.
package bucket

import (
	"errors"
	"math"
	"time"
)

var (
	ErrInvalidConfig   = errors.New("bucket: invalid config")
	ErrInvalidN        = errors.New("bucket: n must be positive")
	ErrExceedsCapacity = errors.New("bucket: n exceeds capacity")
)

// Limiter is a token bucket.
type Limiter struct {
	capacity float64
	rate     float64
	tokens   float64
	last     time.Time
	now      func() time.Time
}

// New returns a full limiter holding up to capacity tokens, refilled at ratePerSecond.
func New(capacity int, ratePerSecond float64, now func() time.Time) (*Limiter, error) {
	if capacity < 1 || ratePerSecond <= 0 {
		return nil, ErrInvalidConfig
	}
	return &Limiter{capacity: float64(capacity), rate: ratePerSecond, tokens: float64(capacity), last: now(), now: now}, nil
}

func (l *Limiter) refill() {
	t := l.now()
	gained := math.Floor(t.Sub(l.last).Seconds() * l.rate)
	l.tokens += gained
	l.last = t
}

// Allow takes n tokens if they are all available now.
func (l *Limiter) Allow(n int) bool {
	if n <= 0 {
		return false
	}
	l.refill()
	if l.tokens < float64(n) {
		return false
	}
	l.tokens -= float64(n)
	return true
}

// Reserve takes n tokens and returns how long to wait until they are available.
func (l *Limiter) Reserve(n int) (time.Duration, error) {
	l.refill()
	if l.tokens >= float64(n) {
		l.tokens -= float64(n)
		return 0, nil
	}
	missing := float64(n) - l.tokens
	l.tokens = 0
	return time.Duration(missing / l.rate * float64(time.Second)), nil
}

// Tokens returns the current balance.
func (l *Limiter) Tokens() float64 {
	l.refill()
	return l.tokens
}
