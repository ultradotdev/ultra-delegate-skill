export class Latest<T> {
  value: T | undefined;
  loading = false;
  private version = 0;
  async load(work: () => Promise<T>): Promise<void> {
    const version = ++this.version;
    this.loading = true;
    try { const value = await work(); if (version === this.version) this.value = value; }
    finally { if (version === this.version) this.loading = false; }
  }
}
