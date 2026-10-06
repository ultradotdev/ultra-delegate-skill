# kvstore: an in-memory key-value store with nested transactions

Package `kvstore` (module `fixture`, standard library only) is split into:

- `store.go`: `Store`, `New`, `Get`, `Set`, `Delete`, `Count`, `Len`, `ErrNoTransaction`.
- `tx.go`: `Begin`, `Commit`, `Rollback`, `Depth`.
- `iterator.go`: `Iter`, `Range` and the `Iterator` type (`Next`, `Key`, `Value`).

Keys and values are strings. The *committed data* is what remains when no transaction is
open. The *view* is what reads see: the innermost open transaction's changes over those of
its enclosing transaction, and so on down to the committed data, where the innermost change
to a key wins. A key is *visible* when the view has a value for it.

## Basics

R1. `New()` returns an empty store: `Get` of any key returns `("", false)`, `Count` of any value is 0, `Len()` is 0 and `Depth()` is 0.
R2. `Set(k, v)` makes `Get(k)` return `(v, true)`; setting a key again overwrites it. The empty string is a valid key and a valid value: after `Set("k", "")`, `Get("k")` returns `("", true)`.
R3. `Delete(k)` makes `Get(k)` return `("", false)`. Deleting a key that is not visible changes nothing.
R4. `Len()` returns the number of visible keys.
R5. `Count(v)` returns the number of visible keys whose visible value is exactly `v`; `Count("")` counts keys whose value is the empty string.
R6. `Count` and `Len` stay correct through overwrites and deletes: overwriting a key from `a` to `b` moves it from `Count(a)` to `Count(b)`, setting a key to its current value changes nothing, and deleting a key removes it from the count of its value.

## Transactions

R7. `Begin()` opens a transaction nested inside the current one, if any. `Depth()` returns the number of open transactions.
R8. While transactions are open, `Set` and `Delete` change only the innermost transaction. `Get`, `Count`, `Len` and new iterators all use the view.
R9. A `Delete` inside a transaction hides the key even when it is visible through an enclosing transaction or the committed data; a later `Set` in the same or a deeper transaction makes it visible again.
R10. `Rollback()` discards the innermost transaction's changes and closes it. Enclosing transactions keep their own changes.
R11. `Commit()` closes the innermost transaction and merges its changes into the enclosing transaction, or into the committed data when it was the outermost. The view is the same before and after. Merged changes belong to the enclosing transaction from then on, so a later `Rollback` of that transaction discards them too.
R12. A delete merged by `Commit` keeps the key hidden: merged into an enclosing transaction it still hides any value further down (in outer transactions or the committed data), and merged into the committed data it removes the key.
R13. `Count` and `Len` always describe the current view, including uncommitted changes. After `Rollback` they describe the restored view, which can include values that come from enclosing transactions rather than from the committed data.
R14. `Commit` and `Rollback` with no open transaction return `ErrNoTransaction` (callers test it with `errors.Is`) and change nothing; otherwise they return `nil`.

## Iterators

R15. `Iter()` returns an `*Iterator` over all visible keys in ascending byte-wise order. `Range(lo, hi)` does the same for the visible keys `k` with `lo <= k < hi`; an empty `hi` means there is no upper bound.
R16. `Next()` advances to the next entry and reports whether there is one; `Key()` and `Value()` return the current entry's key and value. Once `Next()` has returned false it keeps returning false.
R17. An iterator is a snapshot: it yields exactly the keys and values that were visible when `Iter` or `Range` was called. Later `Set`, `Delete`, `Begin`, `Commit` and `Rollback` calls do not change what it yields: keys deleted later are still yielded with their old values, keys added later are not yielded, and keys overwritten later keep their old values.
R18. An iterator created inside a transaction includes the uncommitted changes of every open transaction and omits keys that are deleted in the view. What it yields does not change when that transaction is later rolled back or committed.
R19. Any number of iterators may be in use at the same time, each with its own snapshot and position.
