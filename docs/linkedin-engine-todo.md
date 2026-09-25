# LinkedIn Engine — Project Tracker

This document tracks the implementation of the LinkedIn Engine. It records decisions and completion status without embedding personal user information.

## Status legend

- ⬜ Pending
- 🟡 In progress
- 🔴 Blocked
- ✅ Completed

## Implementation plan

| Step | Description | Status | Evidence / decision |
|---|---|---|---|
| 1 | Define LinkedIn Engine v0.1 scope | ✅ Completed | Capture all accessible results for each configured search. The engine captures; downstream components decide relevance. |
| 2.1 | Select repository architecture | ✅ Completed | Single modular repository with internally independent engines. |
| 2.2 | Create repository | ✅ Completed | `job-radar-platform` repository created. |
| 2.3 | Create modular directory structure | ✅ Completed | LinkedIn `input`, `core`, `output`, `config`, `tests`; shared `data`, `logs`, `docs`, and workflows structure. |
| 2.4 | Create initial README | ✅ Completed | Architecture, principles, planned engines, portability and security documented. |
| 2.5 | Verify repository architecture | ✅ Completed | Repository and LinkedIn Engine directory structure verified against the approved design. |
| 2.6 | Update documentation and TO DO | ✅ Completed | Project tracker created. |
| 2.7 | Close architecture setup | ✅ Completed | Architecture phase closed before functional implementation. |
| 3.1 | Define minimum search fields | ✅ Completed | `search_id`, `keywords`, `location`, `date_posted`. |
| 3.2 | Define optional filters | ✅ Completed | No additional filters in v0.1; broad capture is intentional. |
| 3.3 | Define validation and execution states | ✅ Completed | Two states only: `SUCCESS` and `ERROR`; errors carry cause and recovered-record information where applicable. |
| 3.4 | Select initial input representation | ✅ Completed | YAML is the first adapter; the core remains storage-independent. |
| 3.5 | Create first real test search | ✅ Completed | `Project Manager` + `Barcelona, España` + `past_24_hours`. |
| 3.6 | Implement and document input contract | ✅ Completed | YAML configuration and input-contract documentation committed. |
| 3.7 | Implement and execute contract tests | ✅ Completed | Automated tests executed successfully in GitHub Actions. |
| 3.8 | Close input contract | ✅ Completed | Input boundary validated and ready for downstream search generation. |
| 4 | LinkedIn search request / URL generation | 🟡 In progress | Convert validated search definitions into deterministic LinkedIn search requests without performing extraction yet. |

## Approved architectural rules

1. The base platform must remain generic and portable.
2. Personal identity and professional-profile information must not be hard-coded into the architecture or core engine.
3. Input, core processing and output must remain decoupled.
4. Each engine must be independently replaceable and evolvable.
5. The LinkedIn Engine is a collection engine, not a relevance-selection engine.
6. Extraction should attempt to capture all accessible results returned by each configured search.
7. Failure of one search must not prevent other configured searches from executing.
8. Credentials, tokens, cookies and secrets must never be committed to the repository.
9. The LinkedIn Engine has no memory of rejection, application or AI/human decisions. That state belongs downstream.
10. LinkedIn `job_id` must be preserved in extraction output when available so downstream components can track job state independently.
11. Daily search recency is configuration data (`past_24_hours` in v0.1), not hard-coded core behavior.
12. If extraction is known or reasonably detected to be incomplete, the execution must not silently report `SUCCESS`.

## Current gate

Build and validate the **LinkedIn search request / URL generator**. This phase does not yet claim that real LinkedIn job data has been extracted.
