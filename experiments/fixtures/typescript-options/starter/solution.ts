export function normalizeOptions(value: any) {
 return {limit: Number(value.limit || 20),offset: Number(value.offset || 0),label: String(value.label || '')};
}
