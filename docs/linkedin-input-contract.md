# LinkedIn Engine — Input Contract v1

## Purpose

This contract defines the information the LinkedIn Engine receives for each search. The contract is independent from the storage mechanism: YAML is the initial adapter, but future inputs may come from an API, database or user interface without changing the core extraction logic.

## Required fields

| Field | Purpose |
|---|---|
| `search_id` | Unique internal identifier for the configured search. |
| `keywords` | Free text sent as the LinkedIn search expression. It is not treated as a normalized job title. |
| `location` | Geographic search expression supplied to LinkedIn. |
| `date_posted` | Time window requested for the search. |

## v0.1 operating rule

Daily searches use:

```yaml
date_posted: "past_24_hours"
```

This value belongs to the search configuration and must not be hard-coded into the core engine.

## Filters

v0.1 intentionally applies no additional filters. The collection strategy is broad capture followed by downstream analysis and selection.

## Example

```yaml
version: 1

searches:
  - search_id: SEARCH_001
    keywords: "Project Manager"
    location: "Barcelona, España"
    date_posted: "past_24_hours"
```

## Execution status

Each configured search finishes with one of two states:

- `SUCCESS`: the search and extraction completed as expected.
- `ERROR`: the search was invalid, incomplete or anomalous.

An `ERROR` must include a useful cause/description and, when applicable, the number of records successfully recovered before the error condition.

An error does not imply that recovered records are invalid. For example, an extraction may recover valid records but still end in `ERROR` if the available result set exceeded the engine's proven extraction capacity.

## Validation principles

- `search_id` must be present and unique within the configuration.
- `keywords` must be present and sufficiently meaningful to execute a useful search.
- `location` must be present.
- `date_posted` must contain a supported value.
- Invalid searches must not prevent other valid configured searches from running.
- The engine must not silently report success when it knows or reasonably detects that extraction was incomplete.

Exact technical thresholds (for example minimum keyword length or maximum reliably extractable result count) will be established through implementation and testing rather than assumed in the contract.

## Responsibility boundary

The LinkedIn Engine does not maintain job-decision history. It does not decide whether a job was previously rejected, selected, applied to, or filtered by an intelligence layer.

A LinkedIn job identifier (`job_id`) will be captured as part of extraction output when available so downstream components can maintain job state and human/AI decision history independently from the extractor.
