# TEST PLAN - ASF Scheduler

This plan covers local runs, Streamlit UI, Excel automation, and OneDrive Graph mode.

## Scope
- Data loading: Tableau de bord, Planning benevoles, Vols.
- Planning generation, exports (XLSX/PDF), and write-back to MAG CENTRAL.
- Communication flows: emails, attachments, PDF detection.
- Shipments update (replan/cancel) and Excel updates.
- OneDrive Graph mode (download/upload/list).
- Excel automation (preserve validations and conditional formatting).

## Prerequisites
- Python venv active.
- Excel installed (Mac or Windows) for automation tests.
- OneDrive Graph credentials available (client_id, tenant_id) if Graph mode is tested.
- Sample data files available (real files from production if possible).

## Test Data
- A Tableau de bord file with:
  - MAG CENTRAL sheet
  - New columns W/X/Y/Z headers in row 6
- Planning benevoles file with ParamBenev + Disponibilites.
- Vols file (Vols sheet).
- At least 1 week of BE in status D.

## Automated Tests
Run from repo root:
```
pytest
```
Targeted:
```
pytest tests/test_loaders.py
pytest tests/test_planning_schema.py
pytest tests/test_core_scheduler.py
```

## Manual Tests - Local UI
1) Inputs tab
   - Load sources (tdb/benev/vols).
   - Refresh Graph files (if Graph mode on).
   - Verify warnings are shown for missing/invalid files.
2) Planning V2 (OR-Tools) tab
   - Run the OR-Tools simulation (2 modes).
   - Verify planning preview (BE YYNNNN, Vol AF XXX).
   - Export XLSX and PDF.
   - If "write to source Excel" enabled:
     - MAG CENTRAL columns J/L updated.
     - MAG CENTRAL columns W/X/Y/Z populated from planning.
3) Communication tab
   - Preview enriched planning.
   - Generate email drafts for destination + expediteur.
   - Attach PDF from local or Graph listing.
4) Shipments update
   - Cancel a BE and replan another.
   - Verify Export planning + Planning sheets updated.
5) Params + Manual
   - Edit ParamDest/ParamBE/ParamBenev.
   - Edit Vols and BE in manual tab.
   - Verify save preserves validations + conditional formatting.

## Manual Tests - Critical Business Scenarios
1) Multi-stop routing allocation and display
   - Example flight: `CDG-SSG-DLA`.
   - Expected allocation behavior:
     - `CDG-SSG` and `CDG-DLA` are candidate destinations.
     - One physical flight (same date/time/number) can serve only one destination.
     - In conflict, first routing destination wins.
   - Expected display behavior:
     - Routing shown in UI/export remains the real routing (`CDG-SSG-DLA`), not a simplified destination-only routing.
2) Missing stop in ParamDest
   - A stop in routing is absent from `ParamDest` (ex: `SSG`) while final destination exists (ex: `DLA`).
   - Expected: destination present in ParamDest remains planifiable; flight should not be dropped globally.
3) Air France API `timeOriginType`
   - Compare `S`, `M`, `P` for same flight/day.
   - Expected: verify which timestamp feeds departure hour (`scheduled` vs `latestPublished`) and confirm exported planning uses the intended one.

## OneDrive Graph Mode (Streamlit Cloud or local)
1) Device code auth
   - Trigger login, enter code, confirm token cache.
2) File operations
   - List remote directories.
   - Download sources to TMP.
   - Upload outputs (Planning/Bilan).
3) Error handling
   - Revoke token or disconnect network -> verify UI warning.

## Excel Automation
1) Update MAG CENTRAL with Excel automation.
2) Update any sheet via UI (params/manual/shipments update).
3) Verify:
   - Data validations remain.
   - Conditional formats remain.
4) Fallback (no Excel available):
   - Expect warning in UI.
   - Validate data still saved.

## Error Handling / Tolerance
- Missing source files:
  - UI shows error (fail-fast).
  - Session stops until sources are fixed.
- Incorrect BE/Vol formats:
  - Normalize to BE YYNNNN and Vol AF XXX.

## Performance
- Test with large datasets (>= 500 BE).
- Ensure planning generation and export remain acceptable.

## Reporting
For each test case, log:
- Date/time
- Pass/Fail
- Notes or screenshot
- Files used

## Current Quality Snapshot (2026-02-14)
- Automated tests: `1015 passed`
- Coverage hardening scope (`asf_app + scheduler + loaders + utils`): `99.61%`
- Decision: stop on this pass; remaining uncovered branches are low business value and tested only on regression/bug demand.
