export class Latest<T> {
  value: T | undefined;
  loading = false;
  async load(work: () => Promise<T>): Promise<void> {
    this.loading = true;
    try { this.value = await work(); }
    finally { this.loading = false; }
  }
}
