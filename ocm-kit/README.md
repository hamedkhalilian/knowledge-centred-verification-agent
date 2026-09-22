# OCM Run Kit — v4.4 (+ run-2 corrections)

Everything needed to execute one governed source-to-target migration under the
Migration Operating Protocol v4.4 and General Rules rev 2, with real agents.

This kit is **source-agnostic**. It carries the law, the contracts, the agent
briefs, and the controller's verification tools. It deliberately does NOT carry
the source code or the outputs of any previous run: a kit that ships last run's
answers cannot test anything.

## Layout

```
protocol/     the two binding documents (owner's law, unmodified)
contracts/    canonicalisation contract, 6 JSON schemas, controller flow,
              target directives, alias map, run parameters
briefs/       controller / source agent / target agent briefs
tools/        controller verification tools (python) + the R source detector
tools/examples/  run 2's profiler and synthetic generator, kept as worked
              shapes only -- both are irreducibly source-specific and each
              run writes its own
lessons/      what run 2 cost, so run 3 does not repay it
RUN_IN_CLAUDE_CODE.md   the orchestration prompt
```

## The one rule that makes this a test

The source agent and the target agent run in **separate contexts** (R21). The
target agent never sees the source. Only barrier-scanned files cross. If both
sides end up agreeing on checkpoint digests, that agreement is evidence,
because neither could see the other's answer. Break the barrier and the run
still produces numbers — it just stops proving anything.

## What must be declared before a run

Nothing in `contracts/` carries a previous run's names. Four files ship empty
and must be filled, or the tools that read them halt rather than guess:

| File | Declared during | Read by |
|---|---|---|
| `contracts/source_probes.csv` | DISCOVER | the source detector |
| `contracts/detector_spec_bindings.json` | SPECIFY | the R3 gate |
| `contracts/alias_map.json` | SPECIFY | the graph renderer |
| `contracts/run_params.json` | DISCOVER | both agents |

Each stub documents its own shape. `contracts/controller_flow.md` has the exact
invocations and the gate's exit-code contract.

## Provenance note

`protocol/` is the owner's own material, unchanged. Everything in `contracts/`
is a **reconstruction**: the v4.4 zip references `controller.md`, six schemas,
the P01–P21 register and the canonicalisation contract, and contains none of
them. If the originals surface, they supersede these. See
`lessons/run2_lessons.md`, finding 1.

The four contract files above, and four tools, previously carried run 2's
module names, analysis names, field names and decision-phrase patterns despite
the claim two sections up. The R3 gate reported `AGREE` on a source it had not
read, and the source detector halted on ordinary R. All are fixed here and
recorded as pre-flight findings 9–12 in `lessons/run2_lessons.md`. The tests in
`tests/test_ocm_detector_gate.py` and `tests/test_ocm_r_detector.py` hold the
line: one of them asserts that no tool in `tools/` contains a previous run's
identifiers.
