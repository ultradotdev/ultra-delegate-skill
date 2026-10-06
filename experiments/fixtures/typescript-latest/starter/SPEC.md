# class Latest<T>

`task.ts` exports `Latest<T>`, which runs async loads where only the most recently
started load counts ("last request wins"). No dependencies; Node runs the TypeScript
directly with native type stripping.

A load is *current* while no later `load` call has been started on the same instance;
once a later load starts, the earlier one is *superseded*.

R1. The public API is unchanged: `export class Latest<T>` with public fields `value: T | undefined` (initially `undefined`) and `loading: boolean` (initially `false`), and the method `load(work: () => Promise<T>): Promise<void>`. Calling `load` sets `loading` to `true` synchronously and calls `work()` once.
R2. When the current load's work resolves, `value` becomes the resolved value, `loading` becomes `false`, and the promise returned by that `load` call resolves.
R3. A superseded load never writes `value`, even if its work resolves after the newer load has finished; its returned promise still resolves.
R4. A superseded load never writes `loading`: if it settles (resolves or rejects) while the current load is still pending, `loading` stays `true`.
R5. If a load's work rejects, the promise returned by that `load` call rejects with the same error and `value` is left unchanged; if that load is current, `loading` becomes `false`. A superseded load's promise rejects with its own error too.
