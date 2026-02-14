# Quality Dashboard

- Generated: 2026-02-14 11:43:40 CET
- ISO week: 2026-W07
- Branch: `main`
- Commit: `9b8ff75`

## Current Snapshot

| Metric | Value |
|---|---|
| Tests collected | 1015 |
| Coverage total | 99.61 |
| Coverage target | 75% |

## Coverage Decision

- Current pass is intentionally stopped at `99.61%`.
- Remaining uncovered lines are mostly low-value defensive/UI fallback branches.
- Additional tests will be added only on concrete bug/regression needs.

## Quality Gates

| Gate | Status |
|---|---|
| Ruff | fail |
| Mypy | pass |
| Coverage | pass |
| Secrets | pass |
| Dependency audit | not_run |

## Lowest Coverage Modules

| Module | Coverage % | Lines |
|---|---:|---:|
| `benevole_utils.py` | 96.67 | 30 |
| `services/shipments_update_service.py` | 97.92 | 337 |
| `ui/ui_communication/clean_planning_df.py` | 98.43 | 127 |
| `ui/ui_week_data.py` | 98.76 | 241 |
| `services/export_service.py` | 98.87 | 708 |
| `load_vols_api.py` | 98.88 | 178 |
| `ui/ui_inputs.py` | 98.90 | 362 |
| `load_shipments.py` | 98.99 | 198 |
| `ui/ui_shipments_update_helpers.py` | 99.00 | 798 |
| `ui/ui_logs.py` | 99.26 | 135 |

## Weekly History

| Generated | Week | Branch | Commit | Tests | Coverage | Target | Ruff | Mypy | Coverage Gate | Secrets | Deps |
|---|---|---|---|---:|---:|---:|---|---|---|---|---|
| 2026-02-13 22:52:20 CET | 2026-W07 | main | 0f74296 | 566 | 85.73 | 75 | pass | pass | pass | pass | not_run |
| 2026-02-13 23:05:00 CET | 2026-W07 | main | 0f74296 | 612 | 87.76 | 75 | pass | pass | pass | pass | not_run |
| 2026-02-13 23:08:30 CET | 2026-W07 | main | 0f74296 | 620 | 87.92 | 75 | pass | pass | pass | pass | not_run |
| 2026-02-13 23:15:20 CET | 2026-W07 | main | 0f74296 | 653 | 88.9 | 75 | pass | pass | pass | pass | not_run |
| 2026-02-13 23:19:59 CET | 2026-W07 | main | 0f74296 | 670 | 89.29 | 75 | pass | pass | pass | pass | not_run |
| 2026-02-13 23:29:51 CET | 2026-W07 | main | 0f74296 | 693 | 90.03 | 75 | pass | pass | pass | pass | not_run |
| 2026-02-13 23:40:46 CET | 2026-W07 | main | 0f74296 | 718 | 91.08 | 75 | pass | pass | pass | pass | not_run |
| 2026-02-13 23:45:12 CET | 2026-W07 | main | 0f74296 | 729 | 91.46 | 75 | pass | pass | pass | pass | not_run |
| 2026-02-14 10:28:17 CET | 2026-W07 | main | 9b8ff75 | 874 | 95.02 | 75 | fail | pass | pass | pass | not_run |
| 2026-02-14 10:50:16 CET | 2026-W07 | main | 9b8ff75 | 931 | 97.0 | 75 | fail | pass | pass | pass | not_run |
| 2026-02-14 11:22:35 CET | 2026-W07 | main | 9b8ff75 | 998 | 99.02 | 75 | fail | pass | pass | pass | not_run |
| 2026-02-14 11:43:40 CET | 2026-W07 | main | 9b8ff75 | 1015 | 99.61 | 75 | fail | pass | pass | pass | not_run |
