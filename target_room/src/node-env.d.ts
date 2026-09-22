// Minimal ambient declarations for the Node standard-library surface this
// project uses.
//
// Why these are hand-written: target directive 3 sets the dependency budget at
// ZERO runtime dependencies, with the TypeScript compiler as the single
// allow-listed BUILD-TIME exception. Adding `@types/node` would be a second
// build-time dependency. Declaring the handful of standard-library entry points
// we actually use keeps the budget provably at one, and the list below doubles
// as an explicit inventory of every platform call this program makes.

declare class Buffer extends Uint8Array {
  static alloc(size: number): Buffer;
  static from(data: string, enc?: string): Buffer;
  static from(data: Uint8Array): Buffer;
  static concat(list: Buffer[], total?: number): Buffer;
  static compare(a: Buffer, b: Buffer): number;
  toString(enc?: string, start?: number, end?: number): string;
  subarray(start?: number, end?: number): Buffer;
  compare(other: Buffer): number;
}

declare module "node:fs" {
  export function openSync(path: string, flags: string): number;
  export function readSync(fd: number, buffer: Buffer, offset: number, length: number, position: number | null): number;
  export function closeSync(fd: number): void;
  export function existsSync(path: string): boolean;
  export function statSync(path: string): { size: number; isFile(): boolean; isDirectory(): boolean };
  export function readFileSync(path: string, enc: string): string;
  export function writeFileSync(path: string, data: string, enc: string): void;
  export function mkdirSync(path: string, opts: { recursive: boolean }): void;
  export function readdirSync(path: string): string[];
}

declare module "node:path" {
  export function join(...parts: string[]): string;
  export function resolve(...parts: string[]): string;
  export function dirname(p: string): string;
  export function basename(p: string): string;
  export function isAbsolute(p: string): boolean;
}

declare module "node:crypto" {
  export interface Hash {
    update(data: Buffer | string): Hash;
    digest(enc: string): string;
  }
  export function createHash(algo: string): Hash;
}

declare const process: {
  argv: string[];
  cwd(): string;
  exit(code?: number): never;
  stdout: { write(s: string): boolean };
  stderr: { write(s: string): boolean };
  env: { [k: string]: string | undefined };
};

declare const console: {
  log(...a: unknown[]): void;
  error(...a: unknown[]): void;
};

declare class TextDecoder {
  constructor(label?: string, opts?: { fatal?: boolean; ignoreBOM?: boolean });
  decode(input?: Uint8Array, opts?: { stream?: boolean }): string;
}
declare class TextEncoder {
  encode(input?: string): Uint8Array;
}
