export type QueryScalar = string | number | boolean;
export type QueryValue = QueryScalar | QueryScalar[] | null | undefined;

export function buildQuery(params: Record<string, QueryValue>): string {
  const parts: string[] = [];
  for (const key of Object.keys(params)) {
    const value = params[key];
    if (!value) continue;
    if (Array.isArray(value)) {
      parts.push(`${encodeURIComponent(key)}=${value.map(String).join(',')}`);
    } else {
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
    }
  }
  return parts.join('&');
}
