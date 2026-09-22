// src/logging.ts
//
// GR-08 / GR-10 / R16: nothing is skipped, ignored or fallen back from in
// silence, and any stage that can exceed a few seconds on real data reports
// progress with counts and a percentage.
//
// Every declined input is recorded WHERE IT HAPPENS, with a reason derived from
// the value at hand (R14), and the notices are also carried into the run report
// so that they survive the terminal.

import { intText } from "./canonical.js";

export interface Notice {
  kind: "declined" | "fallback" | "ignored" | "warning" | "info";
  where: string;
  what: string;
  why: string;
  rowIndex: number | null;
  column: string | null;
}

export class Journal {
  public readonly notices: Notice[] = [];
  private counts = new Map<string, number>();
  private echoed = new Set<string>();

  note(n: Notice): void {
    this.notices.push(n);
    const key = n.kind + "|" + n.where + "|" + n.why;
    this.counts.set(key, (this.counts.get(key) ?? 0) + 1);
    // Echo the first occurrence of each distinct reason immediately; the full
    // list goes to the run report. A per-row echo on 45,881 rows would bury the
    // signal it exists to raise.
    if (!this.echoed.has(key)) {
      this.echoed.add(key);
      process.stderr.write(
        "[notice] " + n.kind + " at " + n.where +
        (n.rowIndex !== null ? " row " + intText(n.rowIndex) : "") +
        (n.column !== null ? " column " + n.column : "") +
        ": " + n.what + " -- " + n.why + "\n",
      );
    }
  }

  summary(): Array<{ key: string; count: number }> {
    return Array.from(this.counts.entries())
      .map(([key, count]) => ({ key, count }))
      .sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
  }
}

export class Progress {
  private last = 0;
  private started = Date.now();
  constructor(private readonly stage: string, private readonly total: number | null) {}

  tick(done: number): void {
    const now = Date.now();
    if (now - this.last < 1000 && done !== this.total) return;
    this.last = now;
    const pct =
      this.total && this.total > 0 ? " (" + intText(Math.floor((done * 100) / this.total)) + "%)" : "";
    process.stdout.write(
      "[progress] " + this.stage + ": " + intText(done) +
      (this.total ? " of " + intText(this.total) : "") + pct + "\n",
    );
  }

  done(count: number): void {
    process.stdout.write(
      "[progress] " + this.stage + ": " + intText(count) + " complete in " +
      intText(Date.now() - this.started) + " ms\n",
    );
  }
}
