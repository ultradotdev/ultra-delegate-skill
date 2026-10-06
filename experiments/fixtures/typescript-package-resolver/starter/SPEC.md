# Package resolver

`install(registry, dependencies)` (`src/index.ts`) resolves a root package's dependencies
(an object mapping names to ranges) against a `Registry` (`src/registry.ts`) and returns
`{ versions, order }`: `versions` maps every selected package name to its selected version,
and `order` is the install order as `name@version` strings. `src/index.ts` also exports
`Registry`, `satisfies(version, range)`, `compareVersions(a, b)` and the error classes of
`src/errors.ts`.

Whenever this spec says *sorted* or *smallest* for names, it means plain string order
(JavaScript's `<` on strings, as used by `Array.prototype.sort()` without a comparator).

## Versions

R1. A version is `MAJOR.MINOR.PATCH`: three non-negative decimal integers without leading zeros (`0` itself is fine). Anything else (`1.2`, `v1.2.3`, `01.2.3`, `1.2.3-beta`) throws `InvalidVersionError`. `compareVersions(a, b)` returns a negative number, 0 or a positive number by comparing major, then minor, then patch, numerically.

## Ranges

R2. A range is one or more alternatives separated by `||`; a version satisfies the range if it satisfies any alternative. An alternative is one or more comparators separated by whitespace, all of which must hold. An operator may be followed by whitespace (`>= 1.2.0`). A range that is empty or only whitespace matches every version; any other empty alternative is invalid.
R3. A partial version has one to three dot-separated parts, each a number without leading zeros or a wildcard `x`, `X` or `*`; once a part is a wildcard, all later parts must be wildcards too, and missing parts count as wildcards. With no operator, or with `=`: `*` matches every version, `1` (also `1.x`, `1.x.x`) means `>=1.0.0 <2.0.0`, `1.2` (also `1.2.x`) means `>=1.2.0 <1.3.0`, and `1.2.3` means exactly 1.2.3.
R4. Caret ranges allow changes that keep the leftmost non-zero part: `^1.2.3` means `>=1.2.3 <2.0.0`, `^0.2.3` means `>=0.2.3 <0.3.0` and `^0.0.3` means `>=0.0.3 <0.0.4`. With wildcards: `^1.2` means `>=1.2.0 <2.0.0`, `^0.2` means `>=0.2.0 <0.3.0`, `^0.0` means `>=0.0.0 <0.1.0`, `^1` means `>=1.0.0 <2.0.0`, `^0` means `>=0.0.0 <1.0.0`, and `^*` matches every version.
R5. Tilde ranges allow patch changes: `~1.2.3` means `>=1.2.3 <1.3.0`, `~1.2` means `>=1.2.0 <1.3.0`, `~1` means `>=1.0.0 <2.0.0`, and `~*` matches every version.
R6. `>`, `>=`, `<` and `<=` need a partial version whose major part is a number. With a full version they mean what they say; with a partial one: `>=1.2` means `>=1.2.0`, `<1.2` means `<1.2.0`, `>1.2` means `>=1.3.0`, `<=1.2` means `<1.3.0`, `>1` means `>=2.0.0` and `<=1` means `<2.0.0`.
R7. Anything else is invalid and throws `InvalidRangeError` with the message `invalid range: "<the range as given>"`; for example `^`, `>=`, `>=*`, `1.2.3.4`, `01.2`, `1.x.3`, `1.2.3-beta`, `1.0.0 - 2.0.0`, `abc`, `1 ||` and `>=1.0.0<2.0.0`.

## Registry

R8. `publish(name, version, { dependencies?, peerDependencies? })` checks the version (R1) and every range in the manifest (R7), and throws an `Error` if that version of the package is already published. `versions(name)` returns the published versions in ascending version order (R1), whatever order they were published in; an unknown package has no versions.

## Resolution

R9. Every package gets exactly one version. Names are processed from a first-in, first-out queue: it starts with the root's dependency names in sorted order, and whenever a version is selected, each of its dependency names, in sorted order, that has never been queued is added to the end. Peer dependencies are never queued and play no part in choosing versions.
R10. A request is a (range, requester) pair. The root makes one for each of its dependencies before anything is selected (in sorted name order), and a selected version makes one for each of its dependencies (in sorted name order) right after it is selected. When a name is taken from the queue, it gets the highest published version that satisfies every request made for it so far.
R11. If no published version satisfies those requests, `install` throws `NoMatchingVersionError` with the message `no version of <name> satisfies <range> (from <requester>), <range> (from <requester>), ...`, listing the requests in the order they were made. The root is written `<root>` and a package as `name@version`.
R12. A request for a name whose version has already been selected must be satisfied by that version; otherwise `install` throws `VersionConflictError` with the message `<name>@<selected version> does not satisfy <range> required by <requester>`.
R13. Every root range is checked (R7) before resolution starts.
R14. The result does not depend on the order in which versions were published or in which names appear in a `dependencies` or `peerDependencies` object.

## Peer dependencies

R15. After resolution, peer dependencies are checked for the selected packages in sorted name order, and for each package its peers in sorted order. A peer must be a selected package and its selected version must satisfy the range. The first failing check throws `PeerDependencyError` with the message `<name>@<version> requires peer <peer>@<range>, but <peer> is not installed`, or `<name>@<version> requires peer <peer>@<range>, but <peer>@<selected version> is installed`.

## Install order

R16. `order` lists every selected package exactly once, each one after all of its dependencies and all of its peer dependencies.
R17. Among the packages whose dependencies and peer dependencies are all already listed, the one with the smallest name comes next.
R18. If the dependencies and peer dependencies of the selected packages form a cycle, `install` throws `DependencyCycleError`. Its `cycle` property lists the names along the cycle with the first name repeated at the end, each name depending on (or having as a peer) the next one; its message is `dependency cycle: ` followed by those names joined with ` -> `, e.g. `dependency cycle: a -> b -> a`.
R19. The reported cycle is found by a depth-first search that starts from the selected names in sorted order and visits each package's dependencies and peer dependencies together in sorted order; the first edge that leads back to a package on the current search path closes the cycle. The list is then rotated so that it starts (and ends) with its smallest name.
R20. The checks happen in this order: root ranges (R13), resolution (R10-R12), peer dependencies (R15), install order and cycles (R16-R19).
