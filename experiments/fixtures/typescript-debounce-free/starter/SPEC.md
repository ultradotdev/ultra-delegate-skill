# buildQuery(params: Record<string, QueryValue>): string

`query.ts` exports `buildQuery`, which turns a parameter object into a URL query
string. `QueryValue` is `string | number | boolean | null | undefined` or an array of
`string | number | boolean`. No dependencies; Node runs the TypeScript directly with
native type stripping.

R1. The result is the emitted `key=value` pairs joined with `&`, with no leading `?` and no trailing `&`; when no pair is emitted the result is the empty string.
R2. Keys are the own enumerable string keys of `params` (`Object.keys`), emitted in ascending order of UTF-16 code units, i.e. the order of `Array.prototype.sort()` with no comparator (so `"10"` comes before `"9"` and `"B"` before `"a"`).
R3. Both the key and the value are encoded with `encodeURIComponent` (so a space becomes `%20`, `&` becomes `%26`, `=` becomes `%3D`, and non-ASCII characters become UTF-8 percent escapes).
R4. A string value is used as is; a number is converted with `String(n)`; a boolean becomes `true` or `false`. Falsy values such as `0`, `false` and `""` are emitted like any other value.
R5. A key whose value is `null` or `undefined` is omitted entirely.
R6. An array value emits one pair per element, in array order, each with the same key and no brackets (`{tag: ["a", "b"]}` gives `tag=a&tag=b`); an empty array emits nothing.
R7. A number that is not finite (`NaN`, `Infinity`, `-Infinity`), whether a direct value or an array element, throws RangeError.
R8. An empty string value emits the key followed by `=` and nothing else (`a=`).
