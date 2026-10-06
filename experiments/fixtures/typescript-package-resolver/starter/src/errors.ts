class NamedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

export class InvalidVersionError extends NamedError {
  constructor(version: string) {
    super(`invalid version: "${version}"`);
  }
}

export class InvalidRangeError extends NamedError {
  constructor(range: string) {
    super(`invalid range: "${range}"`);
  }
}

export class NoMatchingVersionError extends NamedError {}

export class VersionConflictError extends NamedError {}

export class PeerDependencyError extends NamedError {}

export class DependencyCycleError extends NamedError {
  cycle: string[];

  constructor(cycle: string[]) {
    super(`dependency cycle: ${cycle.join(' -> ')}`);
    this.cycle = cycle;
  }
}
