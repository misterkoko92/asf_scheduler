# Hardening Audit Report

- Generated: 2026-02-12 21:50:26 CET
- Python files scanned: 98

## Largest Files
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/solver_ortools_v3.py`: 1300 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_stats/ui_stats.py`: 1205 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_shipments_update_helpers.py`: 1139 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/solver_ortools.py`: 1106 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_simulation.py`: 1058 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/services/export_service.py`: 1026 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_shipments_update.py`: 743 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_update.py`: 666 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/services/shipments_update_service.py`: 661 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/data_sources.py`: 640 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/config_paths.py`: 550 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/utils/datetime_utils.py`: 534 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_inputs.py`: 534 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/ui_communication.py`: 522 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_week_data.py`: 487 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/loaders/load_vols.py`: 398 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/services/airfrance_api.py`: 386 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/services/be_placement_service.py`: 379 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_params.py`: 367 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/clean_planning_df.py`: 361 lines

## Longest Functions
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_shipments_update.py:201` `render_tab_shipments_update`: 543 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/services/export_service.py:502` `export_planning_excel`: 525 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/ui_communication.py:112` `render_tab_communication`: 411 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_simulation.py:649` `render_tab_simulation`: 410 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/solver_ortools_v3.py:80` `solve_planning_ortools_simulation`: 376 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/solver_ortools.py:79` `solve_planning_ortools_simulation`: 356 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_week_data.py:138` `render_tab_week_data`: 350 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_params.py:75` `render_tab_params`: 293 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/clean_planning_df.py:79` `build_df_comm`: 283 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_inputs.py:289` `render_tab_inputs`: 246 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_stats/ui_stats.py:973` `render_tab_stats`: 233 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/loaders/load_vols.py:105` `load_vols`: 210 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/loaders/load_shipments.py:82` `load_shipments_df`: 195 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/planning_enrichment.py:51` `enrich_planning`: 184 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_update.py:207` `render_block_add`: 177 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_update.py:35` `render_tab_update`: 166 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/solver_ortools_v3.py:967` `_extract_results`: 165 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_update.py:390` `render_block_modify`: 159 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_logs.py:157` `render_tab_logs`: 154 lines
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_manual.py:58` `render_tab_manual`: 152 lines

## Broad Exception Hotspots
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/services/export_service.py`: 28
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/services/shipments_update_service.py`: 14
- `/Users/EdouardGonnu/asf_scheduler/new_repo/utils/datetime_utils.py`: 14
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_simulation.py`: 13
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_inputs.py`: 13
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_shipments_update_helpers.py`: 12
- `/Users/EdouardGonnu/asf_scheduler/new_repo/loaders/load_vols.py`: 12
- `/Users/EdouardGonnu/asf_scheduler/new_repo/loaders/load_shipments.py`: 12
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_logs.py`: 10
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/services/planning_exports_service.py`: 9
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_stats/ui_stats.py`: 9
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/services/airfrance_api.py`: 8
- `/Users/EdouardGonnu/asf_scheduler/new_repo/loaders/load_vols_api.py`: 8
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_week_data.py`: 7
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/format_rules.py`: 7
- `/Users/EdouardGonnu/asf_scheduler/new_repo/utils/excel_automation.py`: 7
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/state.py`: 6
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_update.py`: 5
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/be_manager.py`: 5
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_params.py`: 4

## Print Call Hotspots
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/audit_comm_planning.py`: 29
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/be_manager.py`: 12
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/config_paths.py`: 12
- `/Users/EdouardGonnu/asf_scheduler/new_repo/loaders/load_vols.py`: 9
- `/Users/EdouardGonnu/asf_scheduler/new_repo/loaders/universal_loader.py`: 6
- `/Users/EdouardGonnu/asf_scheduler/new_repo/loaders/load_shipments.py`: 6
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/be_rules.py`: 5
- `/Users/EdouardGonnu/asf_scheduler/new_repo/loaders/load_benevoles.py`: 5
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_week_data.py`: 4
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_update.py`: 4
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/core_scheduler.py`: 4
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/outlook.py`: 3
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/solver_ortools_v3.py`: 3
- `/Users/EdouardGonnu/asf_scheduler/new_repo/scheduler/solver_ortools.py`: 3
- `/Users/EdouardGonnu/asf_scheduler/new_repo/loaders/load_vols_api.py`: 3
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/email_destinations_handler.py`: 2
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/state.py`: 1
- `/Users/EdouardGonnu/asf_scheduler/new_repo/asf_app/ui/ui_communication/email_expediteurs_handler.py`: 1

## shell=True Occurrences
- none

## Tracked Runtime Artifacts (to review)
- `.vscode/settings.json`
- `Bilan.xlsx`
- `Planning.xlsx`
- `engine_run_stats.json`
- `test_api/export_vols.xlsx`

