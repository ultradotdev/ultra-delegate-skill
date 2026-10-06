# applyBatch(state, operations)

`solution.ts` exports `applyBatch(state, operations)`, which applies a batch of
operations to keyed state and returns the new state. No dependencies; Node runs the
TypeScript directly with native type stripping.

`state` is always a valid array of items `{id, count}` with unique nonempty string ids
and nonnegative safe-integer counts. `operations` is untrusted input. Every rejection
throws a `TypeError`.

R1. `operations` must be an array; anything else (such as `null`, a plain object, a string or a number) throws TypeError.
R2. Each operation must be a plain object: non-null, with prototype `Object.prototype` or `null`. Arrays, class instances (such as a `Date`), `null` and primitives throw TypeError.
R3. An operation's own enumerable keys must be exactly `type`, `id`, `count` when `type` is `"put"`, or exactly `type`, `id` when `type` is `"remove"`. Any other `type` value, a missing key or an extra key throws TypeError.
R4. `id` must be a nonempty string.
R5. A put's `count` must be a number that is a nonnegative safe integer, with no coercion: booleans, numeric strings, `NaN`, fractions, negative numbers and numbers above `Number.MAX_SAFE_INTEGER` throw TypeError.
R6. Operations are applied one after another, in order; each operation sees the result of the ones before it.
R7. A put whose id is already present replaces that item with `{id, count}` at the item's current position.
R8. A put whose id is not present appends `{id, count}` at the end.
R9. A remove deletes the item with that id; removing an id that is not present does nothing.
R10. An id that was removed and is later put again is appended at the end, not restored to its old position.
R11. Ids are compared literally as strings; ids such as `"__proto__"` and `"constructor"` behave exactly like any other id.
R12. The function returns a new array and never mutates `state`, `operations`, any operation object or any existing item object (frozen inputs must work).
R13. Every item in the returned array is a new object, including items that no operation touched; changing the result never changes `state`.
R14. If any operation is invalid, the function throws TypeError and nothing is changed: no partial application is visible in `state`.
