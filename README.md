# Job Radar Platform

Modular platform for automated job discovery, extraction, consolidation and intelligence.

## Purpose

The project is designed as a set of independent engines that can collect job opportunities from different sources, consolidate the extracted data, and later apply matching and intelligence processes.

The platform is intentionally generic: personal profiles, preferences, search criteria, credentials and other user-specific information are treated as external data or configuration and are not embedded in the core architecture.

## Architecture principles

- **Modularity:** each engine has a specific responsibility and can evolve independently.
- **Decoupled input, core and output:** changes to data acquisition or delivery should not require rewriting core logic.
- **Replaceability:** an extractor, storage mechanism or AI provider can be replaced without rebuilding the whole platform.
- **Stable data contracts:** engines communicate through defined data structures rather than implementation details.
- **Traceability:** executions and extracted data must retain enough information to identify their origin and processing status.
- **No silent data loss:** collection and consolidation stages do not discard information based on relevance.
- **Portability:** the base project contains no personal identity or hard-coded professional profile.
- **Security:** credentials, tokens and API keys must never be committed to the repository.

## Planned engines

### LinkedIn Engine

Collects job-search results from configurable LinkedIn searches. It is the first engine being developed and will establish the initial extraction and data-contract patterns.

### Web Engine

Future extraction layer for additional job websites and company career portals using source-specific adapters.

### Merger Engine

Collects outputs from extraction engines and consolidates them into a common dataset. Its role is consolidation and ordering, not relevance assessment.

### Intelligence Engine

Future analysis layer for profile matching, rules, semantic analysis, decision history and auditable learning.

## Current repository structure

```text
job-radar-platform/
├── engines/
│   └── linkedin/
│       ├── input/
│       ├── core/
│       ├── output/
│       ├── config/
│       └── tests/
├── data/
│   └── linkedin/
│       └── raw/
├── logs/
├── docs/
└── .github/
    └── workflows/
```

## LinkedIn Engine design

The LinkedIn Engine follows this conceptual pipeline:

```text
Input / configuration
        ↓
       Core
        ↓
Output / persistence
```

The input layer supplies search definitions and configuration. The core performs search generation and extraction logic. The output layer persists results according to the agreed data contract.

The core must not depend on a particular storage technology. File-based storage may be used initially, while future implementations may use a database or API without requiring core redesign.

## Development status

The project is currently in the initial architecture and LinkedIn Engine development phase.

The first major technical validation gate is to demonstrate that the LinkedIn extraction method can retrieve a sufficiently large result set reliably and repeatedly before investing in downstream functionality.

## Security

Do not commit:

- passwords;
- session cookies;
- access tokens;
- API keys;
- private credentials;
- personal CV/profile data unless an explicit secure storage design has been implemented.

Secrets required by automated workflows must be managed through an appropriate secret-management mechanism such as GitHub Actions secrets.

## License

No license has been selected yet.
