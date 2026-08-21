# Use the Knowledge Verifier on GitHub

The repository-level custom-agent profile is:

```text
.github/agents/knowledge-verifier.agent.md
```

The profile is a small wrapper around the versioned protocol in
`prompts/master_prompt_v2.2.md`. GitHub loads the profile from the selected
repository and branch; the agent then reads the full protocol before doing
substantive work.

## Prerequisites

- A paid GitHub Copilot plan with Copilot cloud agent enabled.
- Access to this repository.
- The agent profile present on the selected branch. For normal use, select
  `main`.

GitHub documents repository custom agents and their availability in the
[custom-agent guide](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/create-custom-agents).

## Start from the GitHub Agents page

1. Open [github.com/copilot/agents](https://github.com/copilot/agents).
2. In the prompt box, select
   `hamedkhalilian/knowledge-centred-verification-agent`.
3. Select the `main` branch.
4. Open the agent picker and select **knowledge-verifier**.
5. Enter a scoped task. State the as-of date, source files, requested outputs,
   and whether you want a pull request.
6. Start the session and inspect the capability declaration before relying on
   any verification result.
7. Review the session log and branch changes. Ask the session to open a pull
   request when the result is ready for repository review.

GitHub's current cloud-agent workflow is described in
[Kick off a task with Copilot agents](https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/kick-off-a-task).

### First smoke-test prompt

```text
Use the knowledge-verifier protocol to inspect
examples/498-bgb/claim-ledger.example.json.

First declare your actual capabilities. Then run the deterministic tests and
kcv-validate against the example. Do not perform or imply external legal
research. Report the gate result and do not change files unless you find a
reproducible defect.
```

### Prompt for a source-backed verification run

Put non-confidential source material in a repository directory such as
`inputs/<matter>/`, then use a prompt like this:

```text
Act as knowledge-verifier.

Matter: <short name>
As-of date: YYYY-MM-DD
Authoritative inputs: inputs/<matter>/
Requested outputs: Claim Ledger JSON, findings JSON, and a Markdown report
Target output directory: runs/<matter>/

Read prompts/master_prompt_v2.2.md in full. Declare capabilities before S0.
Expand research only through actual Claim dependencies. If external retrieval
is unavailable, set external_retrieval = NO and do not claim currentness beyond
the supplied sources. Run kcv-validate, remediate deterministic findings,
regenerate affected outputs, and open a pull request containing the artifacts
and a gate summary.
```

> [!WARNING]
> This repository is public. Do not commit confidential, personal, licensed, or
> client-specific documents. For such material, use a private repository that
> contains the same agent profile and protocol, subject to your organization's
> GitHub and Copilot policies.

## Start from a GitHub issue

1. Create an issue containing the scope, as-of date, input paths, outputs, and
   acceptance criteria.
2. In the issue sidebar, choose **Assignees**, then select **Copilot**.
3. Open the agent dropdown and choose **knowledge-verifier**.
4. Confirm the target repository and base branch, then assign the issue.

Assigning an issue to Copilot creates a pull request. GitHub notes that Copilot
receives the issue text and existing comments at assignment time; later steering
should therefore be added to the resulting pull request.

## Use from GitHub Copilot CLI

From a checkout of the repository, start Copilot CLI and select the repository
agent with:

```text
/agent
```

Then choose `knowledge-verifier`. You can also invoke it directly:

```bash
copilot --agent=knowledge-verifier --prompt "Validate the example ledger and report every release-blocking finding."
```

See GitHub's [Copilot CLI guide](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/overview)
for installation, authentication, and policy prerequisites.

## What the agent can and cannot establish

The default profile can read, search, edit, execute repository code, and use
repository-scoped GitHub tools. It can build ledgers, run the validator,
regenerate repository artifacts, and prepare pull requests.

The `web` tool alias is not currently applicable to Copilot cloud agent.
Arbitrary current legal research therefore requires a configured retrieval MCP
server. Without one, the agent must declare:

```text
external_retrieval = NO
```

It may verify user-supplied primary material as supplied, but currentness,
supersession, and completeness remain limited unless adequate retrieval evidence
is available.

## Troubleshooting

If **knowledge-verifier** does not appear in the picker:

1. Confirm `.github/agents/knowledge-verifier.agent.md` exists on the selected
   branch, normally `main`.
2. Refresh the Agents page after the merge.
3. Confirm the correct repository and branch are selected.
4. Confirm Copilot cloud agent is enabled for the account and repository.

The profile explicitly sets `user-invocable: true`, so it is intended to appear
for manual selection.

## Future retrieval MCP integration

A later profile can add a server under `mcp-servers` and expose its tools.
Secrets must be stored as GitHub Agents secrets or variables, never committed.
The retrieval service should return canonical source URLs, issuers,
jurisdictions, document identifiers, version/effective dates, retrieval times,
content hashes, relevant spans, and license restrictions.
