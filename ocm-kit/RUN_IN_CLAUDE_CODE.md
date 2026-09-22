# Running this in Claude Code

Extract the kit, drop the source to be migrated into `source_room/`, and give
the top-level session the prompt below. That session is the **controller** and
never writes target code itself.

## Before starting — decide four things and record them

1. **Tier**: CORE or FULL. FULL adds the flow manifests, the runtime trace, and
   the rendered + dispositioned graph diff.
2. **Barrier**: structural (separate agent contexts) or single-context. Single
   context caps the verdict at `VERIFIED_TARGET_ONLY` and the sharing must be
   named in the verdict, not inferred.
3. **Scope**: which source files are in this unit.
4. **Findings policy**: faithful only, or faithful default plus corrected
   behaviour behind named switches (R9).

## The orchestration prompt

> You are the CONTROLLER of a governed source-to-target migration under the
> Migration Operating Protocol v4.4 and General Rules rev 2, both in
> `protocol/`. Read them first; they are binding.
>
> Read `briefs/controller_brief.md` for your own role,
> `lessons/run2_lessons.md` for what the previous run cost, and
> `contracts/` for the canonicalisation contract and the schemas every
> artifact must validate against.
>
> The source to migrate is in `source_room/`. Owner decisions:
> tier = <CORE|FULL>, barrier = structural, scope = <files>,
> findings policy = <faithful | faithful + corrected switches>.
>
> Run the states in order: DISCOVER, PROFILE, SPECIFY, OBSERVE_SOURCE,
> IMPLEMENT, OBSERVE_TARGET, COMPARE, VERIFY, VERDICT.
>
> You do not write target code. You spawn two subagents in separate contexts:
> a source agent briefed by `briefs/source_agent_brief.md`, which sees the
> source and never the target; and a target agent briefed by
> `briefs/target_agent_brief.md`, which sees the neutral spec and never the
> source. You mediate every crossing, barrier-scan what flows source to
> target, schema-validate every artifact, and keep `crossing_ledger.md`.
>
> Withhold the source checkpoint values from the target room until the target
> has emitted its own independently. That first comparison is the evidence.

## Subagent invocation

Spawn each agent with the Task tool, one call per role, in its own context.
Give each one only its brief path plus the paths it is allowed to read. State
the prohibition explicitly in the target agent's prompt — "do not read
anything under source_room/, and do not open any <source-language> file
anywhere" — and verify it afterwards by scanning the target tree
(`tools/scan_barrier.py`), because a prohibition nobody checks is a wish.

## Order that actually matters

Profile the inputs **before** the spec is written, and run
`tools/r_source_detector.R` (or its equivalent for the source language) at the
same time. Run 2's single divergence came from a spec that stated a decisive
name list as a count instead of values; the detector had those values and was
run too late to prevent it.
