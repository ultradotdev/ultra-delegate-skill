# bucket.go: token-bucket rate limiter

Package `bucket` (module `fixture`, standard library only) is a token-bucket rate
limiter driven entirely by an injected clock.

```go
var ErrInvalidConfig, ErrInvalidN, ErrExceedsCapacity error

func New(capacity int, ratePerSecond float64, now func() time.Time) (*Limiter, error)
func (l *Limiter) Allow(n int) bool
func (l *Limiter) Reserve(n int) (time.Duration, error)
func (l *Limiter) Tokens() float64
```

The limiter holds a token balance (a float64 that may be fractional, and negative
after `Reserve`) and the **last observed time**. It never reads the real clock;
time comes only from `now()`.

## Requirements

R1. `New` returns `(nil, err)` with `errors.Is(err, ErrInvalidConfig)` unless `capacity >= 1`, `ratePerSecond` is greater than zero and finite (`NaN` and `+Inf` are rejected), and `now` is not nil.

R2. A new limiter starts full: `Tokens()` equals `capacity` and `Allow(capacity)` succeeds before any time passes.

R3. Every call to `Allow`, `Reserve` or `Tokens` first refills: it adds `elapsed seconds × ratePerSecond`, where elapsed is the time since the last observed time (initially the time `now()` returned during `New`), caps the balance at `capacity`, and sets the last observed time to the current `now()`. This happens on every call, including when the bucket is already full and when the call then fails.

R4. Fractional tokens are kept between calls and are never truncated or rounded away: at 0.5 tokens/s, one second after emptying the bucket `Allow(1)` fails (0.5 tokens), and one more second later it succeeds.

R5. If `now()` returns a time earlier than the last observed time (the clock went backwards), the refill adds nothing, removes nothing, and leaves the last observed time unchanged, so time that has already been counted is never counted again when the clock moves forward again.

R6. `Allow(n)` for `1 <= n <= capacity`: if the balance is at least `n`, it subtracts `n` and returns `true`; otherwise it returns `false` and leaves the balance unchanged (no partial consumption).

R7. `Allow(0)` returns `true` and consumes nothing. `Allow(n)` with `n < 0` returns `false`. `Allow(n)` with `n > capacity` returns `false` and consumes nothing, even when the bucket is full.

R8. `Reserve(n)` with `n <= 0` returns an error matching `ErrInvalidN`; with `n > capacity` it returns an error matching `ErrExceedsCapacity`. In both cases the duration is `0` and no tokens are consumed.

R9. `Reserve(n)` with `1 <= n <= capacity` always succeeds: it subtracts `n` right away, even if that makes the balance negative (debt), and returns how long the caller must wait before using the tokens: `0` if the balance before the call was at least `n`, otherwise `(n − balance before) / ratePerSecond` seconds.

R10. The `Reserve` wait is rounded up to the next whole nanosecond, never truncated: at 3 tokens/s with an empty bucket, `Reserve(1)` returns `333333334ns`.

R11. Debt is repaid by normal refill. While the balance is below `n`, `Allow(n)` fails, and each further `Reserve` waits for all earlier debt as well: with capacity 2 at 1 token/s, `Reserve(2)`, `Reserve(1)`, `Reserve(2)` return `0`, `1s` and `3s`, and the balance is back to `0` three seconds later.

R12. `Tokens()` returns the current balance after refilling (it may be fractional or negative) and consumes nothing.

R13. The balance never exceeds `capacity`, however long the limiter sits idle: after an hour idle, `Allow(capacity)` succeeds and an immediate `Allow(1)` fails.
