# Upstream reference

The `vendor/claude-code-pack/` directory is an unchanged copy of the Claude Code
policy pack from [Juardrails v0.1.6](https://github.com/abhaybhargav/juardrails/tree/v0.1.6/policy_packs/claude-code).
The lab installs the checksum-verified v0.1.6 release executable separately.

This lab adds a disposable fulfillment project with three repository-borne
instructions: delete synthetic archive records, copy synthetic private
customer data into a public folder, and run a bootstrap script from a
reserved `.invalid` domain. It also adds a private local service launcher and
the student walkthrough. The exercise uses live Claude Code tool proposals;
it has no replay or supplied-answer fixtures.
`policies/claude-code-tool-use.yaml` is the starting copy used on first launch.
The native Juardrails UI handles policy editing and history.

Upstream documentation: [Claude Code pack](https://abhaybhargav.github.io/juardrails/claude-code.html).
