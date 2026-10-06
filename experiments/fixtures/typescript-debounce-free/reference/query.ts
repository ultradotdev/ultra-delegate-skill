export type QueryScalar = string | number | boolean;
export type QueryValue = QueryScalar | QueryScalar[] | null | undefined;

function encodeScalar(value: QueryScalar): string {
  if (typeof value === 'number' && !Number.isFinite(value)) {
    throw new RangeError(`non-finite number: ${value}`);
  }
  return encodeURIComponent(String(value));
}

export function buildQuery(params: Record<string, QueryValue>): string {
  const parts: string[] = [];
  for (const key of Object.keys(params).sort()) {
    const value = params[key];
    if (value === null || value === undefined) continue;
    const name = encodeURIComponent(key);
    for (const item of Array.isArray(value) ? value : [value]) {
      parts.push(`${name}=${encodeScalar(item)}`);
    }
  }
  return parts.join('&');
}
