# GitHub custom agent

The repository-level profile is:

```text
.github/agents/knowledge-verifier.agent.md
```

It is a wrapper, not a second copy of the protocol. The wrapper establishes the
agent identity, tool boundary, and non-negotiable invariants, then directs the
agent to read `prompts/master_prompt_v2.2.md`.

## Why the protocol is separate

- GitHub limits the Markdown prompt portion of a custom-agent profile to 30,000
  characters.
- Protocol changes remain reviewable as normal versioned specifications.
- Releases can pin `v2.2`, `v2.3`, or `v3.0` without duplicating agent metadata.
- Code, schemas, tests, and protocol changes can be reviewed together.

## Tool boundary

The profile enables repository read, search, edit, shell execution, and
repository-scoped GitHub tools. GitHub documents the `web` alias, but it is not
currently applicable to the Copilot cloud agent. Therefore the wrapper does not
pretend that unrestricted external research exists.

When no retrieval MCP server is configured, the capability declaration must say:

```text
external_retrieval : NO
```

## Future MCP integration

A later agent profile can add a server under `mcp-servers` and explicitly expose
its tools. Secrets should be referenced through GitHub's Copilot/Agents secrets,
never committed to this repository.

The retrieval service should return stable provenance fields: canonical source
URL, issuer, jurisdiction, document identifier, version or effective date,
retrieval timestamp, content hash, relevant span, and license restrictions.

## Activation

GitHub discovers repository agents after the profile is merged into the default
branch. Select **knowledge-verifier** in Copilot Agents and give it a scoped task.
The agent profile version used for a task follows the repository and branch
commit state.

