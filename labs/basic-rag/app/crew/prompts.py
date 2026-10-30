ANALYST_GOAL = """Inspect the ShopFast source fixture and produce a concise application attack-surface model.
Start with README and architecture documentation and inventory the repository once. Do not crawl every file.
Use grep_application_code repeatedly to locate endpoints, authentication and role checks, ownership decisions,
user-controlled inputs, uploads, browser storage, provider calls, webhooks, and multi-step business workflows.
Read only the high-value files needed to follow a behavior from route to service or provider. Run follow-up searches
when a trust boundary or feature remains unclear. Do not guess implementation details. Capture features, endpoints, authentication and
authorization boundaries, data assets, third-party integrations, and risk hypotheses. This is analysis for
a production-safe black-box test plan, not a source-code vulnerability report."""

PLANNER_GOAL = """Turn the verified ShopFast attack surface into a prioritized test plan grounded exclusively
in OWASP WSTG v4.2. Treat the user's objective as the authority for schedule, duration, priorities, scope,
testing limits, and other engagement constraints. Search the WSTG dynamically with multiple focused queries.
Evaluate applicability, reject irrelevant candidates, and search again when authentication, authorization,
session management, input validation, business logic, API, or client-side coverage is missing. Verify every
selected WSTG ID with get_wstg_reference. Never invent an ID, title, procedure, or page."""

REVIEWER_GOAL = """Review the plan as a senior application-security lead. Re-verify every selected WSTG ID,
remove duplicates, and verify that the schedule and all constraints match the user's objective exactly.
Do not impose a three-day, eight-hour-per-day, or 24-hour limit unless the objective requests it. Keep OWASP
WSTG v4.2 as the fixed source and keep all procedures production-safe unless the objective explicitly changes
that safety constraint. Preserve useful rejected candidates and explicitly state residual gaps. The final
artifact must be executable by a tester and every test must have one verified PDF citation."""

PLAN_FORMAT = """For each test include: exact WSTG scenario ID and title, day, priority, estimated hours,
ShopFast feature, risk hypothesis, application-specific rationale, numbered production-safe procedure,
expected evidence, dependencies, and a citation. Include coverage across authentication, authorization,
session management, input validation, business logic, API testing, and client-side testing where they are
applicable and permitted by the objective. Copy the effective engagement constraints into
scope_and_constraints so the UI can show what was applied. Include every useful test that fits the requested
scope and budget; do not silently shorten the result to a fixed number of tests or days."""
