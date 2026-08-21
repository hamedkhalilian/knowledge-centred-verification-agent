# §498 BGB dependency-led example

This example is intentionally a research map, not a legal conclusion and not a
substitute for verifying the law in force on the run's as-of date.

A request for a complete report on §498 BGB should begin with the provision but
must expand only where claims depend on other material. Typical dependency nodes
may include:

```text
§498 BGB
├── §491 BGB — classification and scope
├── §492 BGB — form and durable-medium requirements
├── §497 BGB — consequences of default
├── §501 BGB — cost consequences after acceleration
├── §512 BGB — mandatory-law / anti-circumvention boundary
├── BGH and OLG decisions — interpretation of the qualified notice
├── legislative history — purpose and amendment history
├── EU consumer- and mortgage-credit law — higher-order requirements
└── currentness sources — amendments and effective dates
```

The accompanying ledger is deliberately small. It demonstrates how a derived
scope conclusion names its premises and derivation rule. It does **not** assert
that the example propositions are a current or complete analysis of §498 BGB.

Run:

```bash
kcv-validate examples/498-bgb/claim-ledger.example.json
```

