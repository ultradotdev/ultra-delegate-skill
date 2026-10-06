# normalizeOptions(value: unknown)

`solution.ts` exports `normalizeOptions`, which validates an untrusted options value and
returns `{limit, offset, label}`. Every rejection throws a `TypeError`. No dependencies;
Node runs the TypeScript directly with native type stripping.

R1. `value` must be a non-null object whose prototype is exactly `Object.prototype` or `null`. Arrays, primitives, `null`, class instances (such as a `Date`) and objects with any other prototype throw TypeError.
R2. Every own enumerable string key of `value` must be `limit`, `offset` or `label`. Any other own key throws TypeError, including own keys named `__proto__` or `constructor` (for example the object from `JSON.parse('{"__proto__":{}}')`).
R3. A field that is not an own property of `value`, or whose own value is `undefined`, takes its default: `limit` 20, `offset` 0, `label` `""`.
R4. Only own properties supply field values; inherited properties never do, including properties present on `Object.prototype`.
R5. `limit` must be a number that is an integer from 1 to 100 inclusive; `NaN`, `Infinity`, fractions and out-of-range numbers throw TypeError.
R6. `offset` must be a number that is a nonnegative safe integer (0 to `Number.MAX_SAFE_INTEGER`).
R7. `label` must be a string of at most 40 UTF-16 code units (`label.length <= 40`; an emoji such as 😀 counts as 2).
R8. No coercion: a field value of the wrong type (such as the string `"2"`, `null` or a boolean) throws TypeError even if it could be converted.
R9. The result is a new object with exactly the keys `limit`, `offset` and `label`. `value` is never mutated (frozen input must work) and the result is never `value` itself.
