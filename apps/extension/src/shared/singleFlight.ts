export class SingleFlight<T> {
  private current: Promise<T> | null = null;

  run(operation: () => Promise<T>): Promise<T> {
    if (this.current) return this.current;
    const current = operation();
    this.current = current;
    const clear = () => {
      if (this.current === current) this.current = null;
    };
    void current.then(clear, clear);
    return current;
  }
}
