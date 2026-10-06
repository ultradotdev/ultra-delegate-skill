import { emptyCart, replay } from './reducer.ts';
import type { CartState } from './reducer.ts';
import type { EventStore } from './store.ts';
import { upcastAll } from './upcast.ts';

export class SnapshotStore {
  #snapshots = new Map<string, CartState[]>();

  save(state: CartState): void {
    const list = this.#snapshots.get(state.cartId) ?? [];
    list.push(state);
    this.#snapshots.set(state.cartId, list);
  }

  /** The snapshot with the highest version, if any. */
  latest(cartId: string): CartState | undefined {
    const list = this.#snapshots.get(cartId) ?? [];
    let best: CartState | undefined;
    for (const snapshot of list) if (!best || snapshot.version > best.version) best = snapshot;
    return best;
  }

  all(cartId: string): CartState[] {
    return [...(this.#snapshots.get(cartId) ?? [])];
  }
}

export function loadCart(store: EventStore, snapshots: SnapshotStore, cartId: string): CartState {
  const snapshot = snapshots.latest(cartId);
  if (snapshot) {
    // Only events written after the snapshot need replaying.
    return replay(store.read(cartId, snapshot.version), snapshot);
  }
  return replay(upcastAll(store.read(cartId)), emptyCart(cartId));
}

export function takeSnapshot(store: EventStore, snapshots: SnapshotStore, cartId: string): CartState {
  const state = loadCart(store, snapshots, cartId);
  snapshots.save(state);
  return state;
}
