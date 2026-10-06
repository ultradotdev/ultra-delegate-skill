import { DependencyCycleError } from './errors.ts';
import type { Registry } from './registry.ts';

/** Install order: prerequisites first, ties broken by name (SPEC R16-R19). */
export function installOrder(registry: Registry, selected: Map<string, string>): string[] {
  const prerequisites = new Map<string, string[]>();
  for (const [name, version] of selected) {
    prerequisites.set(name, Object.keys(registry.get(name, version).dependencies));
  }

  const waiting = new Map([...prerequisites].map(([name, needs]) => [name, new Set(needs)]));
  const order: string[] = [];
  while (waiting.size > 0) {
    const ready = [...waiting].filter(([, needs]) => needs.size === 0).map(([name]) => name).sort();
    if (ready.length === 0) throw new DependencyCycleError(findCycle(prerequisites));
    const next = ready[0];
    waiting.delete(next);
    for (const needs of waiting.values()) needs.delete(next);
    order.push(`${next}@${selected.get(next)}`);
  }
  return order;
}

/** A cycle in the prerequisite graph, as [a, b, ..., a] where each name needs the next. */
export function findCycle(prerequisites: Map<string, string[]>): string[] {
  const state = new Map<string, 'active' | 'done'>();
  const path: string[] = [];

  const visit = (name: string): string[] | null => {
    state.set(name, 'active');
    path.push(name);
    for (const next of prerequisites.get(name) ?? []) {
      if (state.get(next) === 'active') return [...path.slice(path.indexOf(next)), next];
      if (!state.has(next)) {
        const found = visit(next);
        if (found) return found;
      }
    }
    path.pop();
    state.set(name, 'done');
    return null;
  };

  for (const name of prerequisites.keys()) {
    if (!state.has(name)) {
      const found = visit(name);
      if (found) return found;
    }
  }
  throw new Error('no cycle found');
}
