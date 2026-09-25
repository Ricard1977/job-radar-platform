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
| 2.6 | Update documentation and TO DO | ✅ Completed | This tracker records the completed architecture work. |
| 2.7 | Close architecture setup | 🟡 In progress | Pending final closure and transition to the next implementation step. |
| 3 | Define LinkedIn Engine input contract | ⬜ Pending | Define how search profiles enter the engine independently from core extraction logic. |

## Approved architectural rules

1. The base platform must remain generic and portable.
2. Personal identity and professional-profile information must not be hard-coded into the architecture or core engine.
3. Input, core processing and output must remain decoupled.
4. Each engine must be independently replaceable and evolvable.
5. The LinkedIn Engine is a collection engine, not a relevance-selection engine.
6. Extraction should attempt to capture all accessible results returned by each configured search.
7. Failure of one search must not prevent other configured searches from executing.
8. Credentials, tokens, cookies and secrets must never be committed to the repository.

## Next gate

Define the **input contract** for LinkedIn searches before implementing extraction logic.
