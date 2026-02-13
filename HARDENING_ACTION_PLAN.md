# Plan d'Action Durcissement (sans changement métier)

## Objectif
Solidifier le projet (qualité, sécurité, maintenabilité, évolutivité) sans modifier le comportement fonctionnel actuel.

## Garde-fous non régression
- Les règles métier et sorties métier doivent rester inchangées.
- Toute action technique doit être couverte par tests existants ou nouveaux tests ciblés.
- Validation minimale de chaque lot: `pytest -q`.

## Baseline (2026-02-12)
- Tests: `98 passed, 1 skipped`
- Tests collectés: `99`
- Fichiers suivis dans le repo (approx): `244`
- Signaux de complexité (patterns `except/print` dans code + tests): `375`

## État courant (re-baseline 2026-02-13)
- Tests: `446 passed`
- Tests collectés: `446` (`pytest --collect-only -q`)
- Couverture globale locale (`pytest-cov`): `77%` (`8522/11042`)
- Qualité statique:
  - `ruff`: OK (`All checks passed`)
  - `mypy`: OK (`Success: no issues found in 101 source files`)
- Sécurité:
  - `tools/scan_secrets.py`: OK (`no suspicious hardcoded secret found`)
- Hygiène dépôt:
  - artefacts runtime sortis de l’index Git: `Bilan.xlsx`, `Planning.xlsx`, `engine_run_stats.json`, `test_api/export_vols.xlsx`

## Backlog priorisé
1. Audit technique exhaustif (complexité, dette, duplication, robustesse erreurs, sécurité).
2. Renforcement tests métier sur points critiques non couverts.
3. Simplifications internes à faible risque (refactor non-fonctionnel, factorisation).
4. Sécurisation des flux secrets/config et messages d'erreur.
5. Durcissement outillage qualité (CI, checks locaux, documentation d'exploitation).
6. Préparer les lots de refactor lourds (UI monolithique, export monolithique, solveur dupliqué) avec stratégie anti-régression.

## Prochains lots ajustés (priorisés)
1. **P2 clôture technique (terminé sur cette passe)**  
   - job `coverage` CI dédié ajouté (seuil progressif `70%`) et branché en gate avant `build`  
   - outillage local enrichi (`tools/run_quality.py coverage`, hook pre-commit manuel)  
   - palier mypy appliqué (`check_untyped_defs=True`) sur modules UI stabilisés
2. **Couverture résiduelle ciblée (P2 terminé sur modules prioritaires)**  
   - `ui_logs.py`: `39%` -> `82%`  
   - `ui_manual.py`: `24%` -> `94%`  
   - `whatsapp_handler.py`: `49%` -> `92%`  
   - `stats_processor.py`: `47%` -> `94%`
3. **Réduction des monolithes restants (P3)**  
   - extractions non-fonctionnelles additionnelles sur `render_tab_simulation`, `render_tab_week_data`, `render_tab_params`, `render_tab_inputs`  
   - poursuivre la réduction de `ui_shipments_update_helpers.py` (découpage par domaine)
4. **Couverture résiduelle hors P2 (P3)**  
   - modules encore faibles: `ui_logs.py` et `ui_manual.py` sont remontés; restent surtout `asf_app/ui/email_defaults.py`, `asf_app/config/email_defaults.py`, `state_planning.py`
5. **Industrialisation CI avancée (P3)**  
   - monter progressivement le seuil coverage CI (70 -> 75 -> 80) en gardant la stabilité des releases

## Diagnostic global approfondi (2026-02-13)
- Points forts consolidés:
  - zéro hotspot `except Exception` et `print` dans l’audit automatique
  - socle tests en forte progression (`446` tests collectés)
  - factorisation solver V2/V3 avancée via `scheduler/solver_ortools_common.py`
  - gates qualité/sécurité restaurées (`ruff`/`mypy`/`secret-scan` OK) + gate coverage CI dédié
- Risques actifs:
  - **couverture insuffisante** sur quelques modules non critiques UI/config (email defaults, state planning)
  - **monolithes persistants** (fonctions 200-500+ lignes) augmentant le coût de maintenance
  - **outillage sensible aux régressions rapides** (imports/typage/tests outillage sécurité) nécessitant discipline CI
- Top dette technique (taille/fonctions):
  - `asf_app/ui/ui_shipments_update_helpers.py` (~1720 lignes)
  - `asf_app/ui/ui_simulation.py` (~1574 lignes)
  - `asf_app/services/export_service.py` (~1308 lignes)
  - `asf_app/ui/ui_stats/ui_stats.py` (~1205 lignes)
  - solveurs: `scheduler/solver_ortools_v3.py` (~1028), `scheduler/solver_ortools.py` (~829)

## Constats d'audit (en cours)
- Très grosses unités à risque maintenance:
  - `asf_app/ui/ui_shipments_update.py::render_tab_shipments_update` (~512 lignes, après extractions partielles)
  - `asf_app/ui/ui_simulation.py::render_tab_simulation` (~410 lignes, après extraction de helpers)
  - `asf_app/ui/ui_week_data.py::render_tab_week_data` (~350 lignes, après extraction des helpers de vues semaine)
  - `asf_app/ui/ui_communication/ui_communication.py::render_tab_communication` (~208 lignes, après extraction de la sélection source session/OneDrive)
- Modules volumineux:
  - `asf_app/ui/ui_shipments_update.py` (713 lignes, après extraction de helpers queue/notifs/session/sélection BE/vol-bénévole/dispo-BE/prefill/notifications/apply-batch + sélection semaine/version/aperçu)
  - `asf_app/ui/ui_shipments_update_helpers.py` (1720 lignes, helperization UI shipments)
  - `asf_app/services/export_service.py` (~1307 lignes, après extraction des helpers de rendu planning Excel + versioning/sortie + durcissement exceptions techniques)
  - `asf_app/ui/ui_simulation.py` (~1574 lignes, helpers de logique manuelle et bilans enrichis)
  - `asf_app/ui/ui_communication/ui_communication.py` (~474 lignes, logique I/O PDF OneDrive/local encore à extraire)
  - `scheduler/config_paths.py` (~788 lignes, migration `RuntimePaths` finalisée sur `prepare_paths` + cache Graph runtime-aware)
  - `scheduler/solver_ortools_v3.py` (~1028 lignes)
  - `scheduler/solver_ortools.py` (~829 lignes)
  - `scheduler/solver_ortools_common.py` (~730 lignes, noyau commun V2/V3)
- Gestion d'erreurs très large (`except Exception`):
  - aucun hotspot restant dans le code scanné par l’audit
- Duplication solver:
  - noyau commun extrait dans `scheduler/solver_ortools_common.py`; V2/V3 conservent uniquement les branches métier spécifiques.
- Couverture structurelle (approximation imports tests):
  - modules prod détectés: 99
  - importés directement par tests: 47
  - non importés directement: 42 (majoritairement couche UI communication/statistiques)
- Hygiène dépôt:
  - `.env` sorti de l'index Git et `.env*` ignorés
  - règles d’ignore en place et artefacts runtime retirés de l’index (`Planning.xlsx`, `Bilan.xlsx`, `engine_run_stats.json`, `test_api/export_vols.xlsx`)
- Outillage qualité:
  - `pre-commit` + `ruff` + `mypy` actifs en local (stage `pre-commit` + `manual`) avec runner robuste `tools/run_quality.py`
  - CI qualité bloquante activée via job `quality` (pré-requis de `build`)
  - scan secrets activé en gate locale/CI: script `tools/scan_secrets.py`, hook `pre-commit` (`pre-commit` + `manual`), job CI bloquant `security`, allowlist contrôlée `.secret-scan-allowlist`
  - état instantané 2026-02-13 (après P0): gates restaurées (`ruff`, `mypy`, `secret-scan`) et `pre-commit --all-files` vert
- Audit automatisable:
  - script: `tools/hardening_audit.py`
  - rapport généré: `HARDENING_AUDIT_REPORT.md`
- Hotspots `print` résiduels:
  - aucun hotspot restant dans le code scanné par l’audit

## Journal d'actions
| Date/Heure | Action | Résultat |
|---|---|---|
| 2026-02-13 | P2 one-pass: ajout du job CI `coverage` (seuil progressif 70%) + artefact `coverage.xml` | OK |
| 2026-02-13 | P2 one-pass: extension `tools/run_quality.py` avec cible `coverage` + hook pre-commit manuel | OK |
| 2026-02-13 | P2 one-pass: palier mypy strict sur sous-ensemble stable (`ui_logs`, `ui_manual`, `stats_processor`, `whatsapp_handler`) | OK |
| 2026-02-13 | Correctif robustesse `ui_manual`: garde-fou chemins TMP non initialisés (retour UI explicite) | OK |
| 2026-02-13 | P2 one-pass: lot tests couverture (`ui_logs`, `ui_manual`, `stats_processor`, `whatsapp_handler`, outillage quality) | OK |
| 2026-02-13 | Validation finale P2: `446 passed`, `coverage=77%`, gate coverage local `ASF_COVERAGE_MIN=70` vert | OK |
| 2026-02-13 | P1 one-pass: ajout lot tests solveur (`priority_mode` divergent + diagnostic bénévoles incompatibles) | OK |
| 2026-02-13 | P1 one-pass: ajout lot tests UI communication/stats/params + render/smoke `ui_inputs` et `ui_week_data` | OK |
| 2026-02-13 | Correctif robustesse `scheduler/data_sources.py`: mapping `param_benev` stocké en `dict` (suppression truth-value ambiguë pandas) | OK |
| 2026-02-13 | Validation globale qualité: `431 passed`, `coverage=75%`, `ruff` OK, `mypy` OK | OK |
| 2026-02-13 | Régénération audit projet (`tools/hardening_audit.py`) + mise à jour plan d'action | OK |
| 2026-02-12 | Création du plan de durcissement | OK |
| 2026-02-12 | Baseline complète (status git, collecte tests, exécution tests) | OK |
| 2026-02-12 | Audit structurel auto (taille, fonctions longues, exceptions, duplication, couverture structurelle) | OK |
| 2026-02-12 | Audit sécurité/hygiène (secrets, `shell=True`, artefacts suivis) | OK |
| 2026-02-12 | Renforcement tests: `simulation_runner`, handlers email, garde-fous repo | OK |
| 2026-02-12 | Simplification non fonctionnelle: nettoyage imports inutilisés | OK |
| 2026-02-12 | Durcissement sécurité: suppression `shell=True` dans `whatsapp_handler` + tests dédiés | OK |
| 2026-02-12 | Mise en place audit automatisé (`tools/hardening_audit.py`) + rapport `HARDENING_AUDIT_REPORT.md` | OK |
| 2026-02-12 | Génération rapport d'audit à jour (`HARDENING_AUDIT_REPORT.md`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction helpers purs (versioning, week/year, workbook) | OK |
| 2026-02-12 | Renforcement tests helpers export (`tests/test_export_service_helpers.py`) | OK |
| 2026-02-12 | Re-génération audit après refactor (`export_planning_excel` réduit à ~812 lignes) | OK |
| 2026-02-12 | Refactor structurel `ui_simulation`: extraction helpers purs (style/recompute/export util) | OK |
| 2026-02-12 | Renforcement tests helpers simulation (`tests/test_ui_simulation_helpers.py`) | OK |
| 2026-02-12 | Re-génération audit après refactor (`render_tab_simulation` réduit à ~580 lignes) | OK |
| 2026-02-12 | Refactor structurel `shipments_update_service`: extraction helpers MAG CENTRAL (lookup/sélection/ciblage) | OK |
| 2026-02-12 | Renforcement tests helpers MAG CENTRAL (`tests/test_shipments_update_mag_helpers.py`) | OK |
| 2026-02-12 | Re-génération audit après refactor + validation globale (`130 passed, 1 skipped`) | OK |
| 2026-02-12 | Renforcement tests métier `shipments_update_service` (fallbacks champs, annulation/replanification, tri) | OK |
| 2026-02-12 | Validation globale suite de tests (`134 passed, 1 skipped`) + audit régénéré | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction helpers (phrase action, emails, dédup queue, payloads notifications) | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (`tests/test_ui_shipments_update_helpers.py`) | OK |
| 2026-02-12 | Validation globale suite de tests (`142 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~784 lignes) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction helpers queue/session/groupes notifications | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (queue/session/groupes) | OK |
| 2026-02-12 | Validation globale suite de tests (`146 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~746 lignes) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction helpers sélection BE + méta bénévole | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (sélection BE/méta) | OK |
| 2026-02-12 | Validation globale suite de tests (`151 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~630 lignes) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction helpers sélection vol/bénévole (default tuple/options/labels/fallback noms) | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (vol/bénévole) | OK |
| 2026-02-12 | Validation globale suite de tests (`155 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` sorti du top 20 des fonctions les plus longues) | OK |
| 2026-02-12 | Correctif immédiat: régression d'indentation `else` dans `ui_shipments_update` + vérification `py_compile` | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction helpers dispo/BE (`_prepare_dispo`, `_coerce_display_types`, `_bene_status`, `_collect_be_from_planning`, `_find_row_in_df`) | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (dispo/BE) | OK |
| 2026-02-12 | Validation globale suite de tests (`160 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~597 lignes) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction helpers prefill/queue-item (`_pop_prefill_values`, `_build_queue_item`) | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (prefill/queue-item) | OK |
| 2026-02-12 | Validation globale suite de tests (`162 passed, 1 skipped`) + audit régénéré (`163 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction helpers notifications (ASF/Escale/Expéditeur, période, version, PDF, brouillons) | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (notifications) | OK |
| 2026-02-12 | Validation globale suite de tests (`168 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~585 lignes, `169 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction helpers apply-batch (validation queue path, warning duplicats, exécution update, gestion PDF, info MAG CENTRAL) | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (apply-batch) | OK |
| 2026-02-12 | Validation globale suite de tests (`173 passed, 1 skipped`) + audit régénéré (`174 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `ui_week_data`: extraction helpers vues semaine (`_compute_week_dates`, `_build_benev_week_table`, `_build_benev_ranges_by_date`, `_build_flights_week_table`) | OK |
| 2026-02-12 | Renforcement tests helpers UI week data (`tests/test_ui_week_data_helpers.py`) | OK |
| 2026-02-12 | Validation globale suite de tests (`180 passed, 1 skipped`) + audit régénéré (`render_tab_week_data` ~350 lignes, `181 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `ui_simulation`: extraction helpers sélection manuelle (bornes semaine, parsing heure, options BE/vol/bénévole, statut bénévole) | OK |
| 2026-02-12 | Renforcement tests helpers UI simulation (`tests/test_ui_simulation_helpers.py`) | OK |
| 2026-02-12 | Validation globale suite de tests (`186 passed, 1 skipped`) + audit régénéré (`187 tests collectés`) | OK |
| 2026-02-12 | Durcissement parsing dates: filtrage ciblé warning pandas `dayfirst=True` sur ISO dans `utils/datetime_utils.py` | OK |
| 2026-02-12 | Renforcement tests datetime utils (absence de warning sur ISO + `dayfirst=True`) | OK |
| 2026-02-12 | Validation globale suite de tests (`188 passed, 1 skipped`) + audit régénéré (`189 tests collectés`, warnings supprimés sur lot simulation helpers) | OK |
| 2026-02-12 | Refactor structurel `ui_simulation`: extraction helpers édition manuelle (`_build_manual_row_data`, `_apply_manual_assignment`, `_delete_manual_assignment`, `_normalize_sort_plan`) | OK |
| 2026-02-12 | Renforcement tests helpers UI simulation (mutations manuelles du planning) | OK |
| 2026-02-12 | Validation globale suite de tests (`190 passed, 1 skipped`) + audit régénéré (`render_tab_simulation` ~410 lignes, `191 tests collectés`) | OK |
| 2026-02-12 | Durcissement `planning_schema`: normalisation `_MANUEL` sans `fillna(False)` pour supprimer le `FutureWarning` pandas | OK |
| 2026-02-12 | Renforcement tests planning schema (absence de `FutureWarning` sur `_MANUEL`) | OK |
| 2026-02-12 | Validation globale suite de tests (`191 passed, 1 skipped`) + audit régénéré (`192 tests collectés`, warnings supprimés sur lot planning schema) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction helpers purs (mapping affichage bénévoles, normalisation vols, fallback routing) | OK |
| 2026-02-12 | Renforcement tests helpers export (`tests/test_export_service_helpers.py`) | OK |
| 2026-02-12 | Validation globale suite de tests (`195 passed, 1 skipped`) + audit régénéré (`export_planning_excel` ~750 lignes, `196 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction helpers MAG CENTRAL (index/recherche/ordonnancement/écriture) et sortie de `update_mag_central_dates` du corps principal | OK |
| 2026-02-12 | Renforcement tests helpers export MAG CENTRAL (`tests/test_export_service_helpers.py`) | OK |
| 2026-02-12 | Validation globale suite de tests (`202 passed, 1 skipped`) + audit régénéré (`export_planning_excel` ~525 lignes, `203 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction helpers semaine/version/aperçu (`_weeks_from_status_df`, `_build_week_selector_data`, `_build_planning_version_choices`, `_format_preview_dataframe`, `_load_export_planning_sheet`, `_select_source_for_be`) | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (semaine/version/aperçu) | OK |
| 2026-02-12 | Validation globale suite de tests (`206 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~543 lignes, `207 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction helpers transitions file d’attente + orchestration validation batch (`_queue_transition_after_action`, `_execute_queue_apply_request`) | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (transitions queue + orchestration apply) | OK |
| 2026-02-12 | Validation globale suite de tests (`208 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~536 lignes, `209 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: centralisation mutations file d’attente dans la session (`_apply_queue_action_to_session`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction orchestration notifications + envois Outlook + feedback apply (`_prepare_notification_context`, `_send_outlook_draft`, `_send_named_outlook_drafts`, `_build_sent_drafts_feedback`, `_collect_apply_result_feedback`) | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (session queue, feedback apply, contexte notifications, envois drafts) | OK |
| 2026-02-12 | Refactor UI `ui_shipments_update`: intégration des nouveaux helpers dans les branches edit/delete/clear/apply/notifications | OK |
| 2026-02-12 | Validation globale suite de tests (`211 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~524 lignes, `212 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction du contexte d’affectation courant (`_resolve_assignment_from_plan_row`, `_resolve_current_bene_identity`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction sélection d’action + synthèse affichée (`_build_action_selection_data`, `_build_assignment_summary`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction mutation session lors d’ajout file (`_apply_queue_add_to_session`) | OK |
| 2026-02-12 | Durcissement non-fonctionnel `ui_shipments_update`: extraction ouverture OS testable (`_open_file_in_os`) | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (action/contexte BE/synthèse/session add/ouverture OS) | OK |
| 2026-02-12 | Validation globale suite de tests (`216 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~521 lignes, `217 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction préparation dataframe export (`_prepare_export_dataframe`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction fallback date départ MAG (`_resolve_depart_mag_date`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: factorisation écriture des feuilles/tableaux (`_clear_worksheet_tables`, `_add_excel_table_if_needed`, `_write_dataframe_to_sheet`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: factorisation export PDF avec warning (`_export_pdf_with_warning`) | OK |
| 2026-02-12 | Renforcement tests helpers export (`_prepare_export_dataframe`, `_resolve_depart_mag_date`, `_write_dataframe_to_sheet`, `_export_pdf_with_warning`) | OK |
| 2026-02-12 | Validation globale suite de tests (`220 passed, 1 skipped`) + audit régénéré (`export_planning_excel` ~525 lignes, `221 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction chargement sources BE semaine (`_load_be_sources_for_week`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction data sélecteurs BE (`_build_planifiable_be_selector_data`, `_build_lookup_be_selector_data`, `_resolve_lookup_be_row`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: extraction orchestration ajout file d’attente (`_execute_queue_add_request`) | OK |
| 2026-02-12 | Refactor structurel `ui_shipments_update`: factorisation envoi drafts nommés + feedback (`_send_named_outlook_drafts_with_feedback`) | OK |
| 2026-02-12 | Renforcement tests helpers UI shipment update (sources semaine, sélecteurs BE, ajout file, feedback drafts) | OK |
| 2026-02-12 | Validation globale suite de tests (`225 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~512 lignes, `export_planning_excel` ~439 lignes, `226 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction constantes + reset grille planning (`_PLAN_DAY_BLOCKS`, `_PLAN_KEEP_ROWS`, `_PLAN_MIDDLE_MOVES`, `_reset_planning_grid`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction écriture ligne planning + style statut (`_write_planning_row`, `_apply_status_fill`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction remplissage blocs journaliers + masquage (`_populate_planning_sheet`, `_hide_non_keep_rows`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction layout final feuille planning (`_move_cell_value_to_visible_middle`, `_apply_planning_layout`) | OK |
| 2026-02-12 | Renforcement tests helpers export (grille planning, écriture ligne, population blocs, layout final) | OK |
| 2026-02-12 | Validation globale suite de tests (`229 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~512 lignes, `export_planning_excel` ~286 lignes, `230 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction préparation chemin/classeur sortie (`_prepare_output_workbook_path`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction préparation export bénévoles (`_resolve_benevoles_export_dataframe`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction versioning fichiers (`_collect_existing_planning_versions`, `_archive_latest_planning_if_needed`, `_resolve_target_planning_path`) | OK |
| 2026-02-12 | Refactor structurel `export_service`: extraction finalisation version/sauvegarde/sync (`_set_q1_version`, `_increment_q1_if_requested`, `_save_sync_and_move_planning_output`) | OK |
| 2026-02-12 | Renforcement tests helpers export (sortie initiale, bénévoles, versioning, Q1, save/sync/move) | OK |
| 2026-02-12 | Validation globale suite de tests (`234 passed, 1 skipped`) + audit régénéré (`render_tab_shipments_update` ~512 lignes, `export_planning_excel` ~207 lignes, `235 tests collectés`) | OK |
| 2026-02-12 | Refactor non fonctionnel `load_vols`: extraction helper `_normalize_flight_number` (suppression duplication parsing numéros vol) | OK |
| 2026-02-12 | Renforcement tests helpers `load_vols` (`tests/test_load_vols_helpers.py`) | OK |
| 2026-02-12 | Validation globale suite de tests (`241 passed, 1 skipped`) | OK |
| 2026-02-12 | Re-génération audit (`tools/hardening_audit.py`) après lot `load_vols` | OK |
| 2026-02-12 | Refactor structurel `ui_communication`: extraction helpers purs (`ui_communication_helpers.py`) pour mapping destinataire + format dataframe d'aperçu | OK |
| 2026-02-12 | Intégration helpers dans `render_tab_communication` (suppression fonctions imbriquées BE/destinataire/aperçu) | OK |
| 2026-02-12 | Renforcement tests helpers UI communication (`tests/test_ui_communication_helpers.py`) | OK |
| 2026-02-12 | Validation globale suite de tests (`245 passed, 1 skipped`) + audit régénéré (`render_tab_communication` ~340 lignes, `246 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `ui_communication`: extraction orchestration source session/OneDrive en fonctions dédiées (`_load_session_planning_ui`, `_load_onedrive_planning_ui`) | OK |
| 2026-02-12 | Renforcement helpers UI communication (options source session, labels modes simulation, reset cache OneDrive année) | OK |
| 2026-02-12 | Renforcement tests helpers UI communication (source session/simulation + reset année + utilitaires dataframe) | OK |
| 2026-02-12 | Validation globale suite de tests (`250 passed, 1 skipped`) + audit régénéré (`render_tab_communication` ~208 lignes, `251 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `scheduler/config_paths`: ajout snapshot immuable `RuntimePaths` + `get_runtime_paths()` | OK |
| 2026-02-12 | Refactor structurel `scheduler/config_paths`: helpers migrés vers snapshot optionnel (`get_planning_dirs`, `get_planning_maquette_path`, `print_config_paths`, `get_output_remote_dir/path`, `remote_path_for_local`) | OK |
| 2026-02-12 | Renforcement tests `config_paths` (immutabilité snapshot, helpers remote path, résolution runtime explicite) | OK |
| 2026-02-12 | Validation globale suite de tests (`253 passed, 1 skipped`) + audit régénéré (`254 tests collectés`) | OK |
| 2026-02-12 | Refactor structurel `scheduler/config_paths`: extension migration `RuntimePaths` sur helpers I/O (`cleanup_tmp`, `ensure_tmp_up_to_date`, `_copy_to_tmp`, `_download_to_tmp`, `sync_local_file_to_onedrive`) | OK |
| 2026-02-12 | Renforcement tests `config_paths` (cleanup via runtime, ensure_tmp_up_to_date runtime, sync remote mapping via runtime) | OK |
| 2026-02-12 | Validation globale suite de tests (`256 passed, 1 skipped`) + audit régénéré (`257 tests collectés`) | OK |
| 2026-02-12 | Refactor non fonctionnel `loaders/*`: migration `print` métier vers logger homogène (`load_vols`, `load_shipments`, `load_benevoles`, `load_vols_api`, `universal_loader`) | OK |
| 2026-02-12 | Renforcement tests loaders (`tests/test_universal_loader.py`, `tests/test_loaders.py`, `tests/test_load_vols_api.py`) avec assertions `caplog` | OK |
| 2026-02-12 | Validation globale suite de tests (`259 passed, 1 skipped`) + audit régénéré (`260 tests collectés`) | OK |
| 2026-02-12 | Durcissement non fonctionnel `scheduler/config_paths`: `print_config_paths` migré en logs structurés + logger module remonté en tête | OK |
| 2026-02-12 | Durcissement non fonctionnel `scheduler/be_manager`: migration diagnostics ParamBE (`print`) vers logging (`info/debug/warning`) | OK |
| 2026-02-12 | Renforcement tests `config_paths`/`be_manager` (`tests/test_config_paths.py`, `tests/test_be_manager.py`) | OK |
| 2026-02-12 | Validation globale suite de tests (`262 passed, 1 skipped`) + audit régénéré (`263 tests collectés`) | OK |
| 2026-02-12 | Durcissement non fonctionnel `export_service`: remplacement des `except Exception` techniques par exceptions explicites (conversions, I/O workbook, archives/versioning) | OK |
| 2026-02-12 | Simplification non fonctionnelle `export_service`: suppression d’un bloc de validation date sans effet (`fromisocalendar` + `pass`) | OK |
| 2026-02-12 | Validation ciblée `export_service` (`tests/test_export_service_helpers.py`: `32 passed`) | OK |
| 2026-02-12 | Validation globale suite de tests (`262 passed, 1 skipped`) + audit régénéré (`export_service` hotspot `except Exception`: `4`) | OK |
| 2026-02-12 | Durcissement non fonctionnel `scheduler/be_rules`: migration traces priorité/équivalents (`print`) vers logging homogène | OK |
| 2026-02-12 | Renforcement tests `be_rules` (`tests/test_be_rules.py`: vérification `caplog` sur logs priorité/équivalents) | OK |
| 2026-02-12 | Validation globale suite de tests (`263 passed, 1 skipped`) + audit régénéré (`264 tests collectés`, `be_rules` retiré des hotspots print) | OK |
| 2026-02-12 | Durcissement non fonctionnel `shipments_update_service`: remplacement des `except Exception` techniques par exceptions explicites (lecture Excel, parsing, openpyxl I/O) | OK |
| 2026-02-12 | Simplification non fonctionnelle `shipments_update_service`: suppression du `try/except` inutile dans `_from_plan_row` | OK |
| 2026-02-12 | Renforcement tests `shipments_update_service` (`tests/test_shipments_update_service_helpers.py`: fallback `_load_export_df` en Excel invalide) | OK |
| 2026-02-12 | Validation globale suite de tests (`264 passed, 1 skipped`) + audit régénéré (`265 tests collectés`, `shipments_update_service` retiré des hotspots `except Exception`) | OK |
| 2026-02-12 | Durcissement non fonctionnel `datetime_utils`: remplacement des `except Exception` par exceptions explicites (ISO/date/time parsing, `strftime`, conversions numériques) | OK |
| 2026-02-12 | Simplification non fonctionnelle `datetime_utils`: suppression d’un `try/except` redondant dans `parse_date_long_fr` (`coerce_datetime` en `errors='coerce'`) | OK |
| 2026-02-12 | Renforcement tests `datetime_utils` (ISO `Z`, heures décimales, fallback format date/heure) | OK |
| 2026-02-12 | Validation globale suite de tests (`267 passed, 1 skipped`) + audit régénéré (`268 tests collectés`, `datetime_utils` retiré des hotspots `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `loaders/load_shipments` et `loaders/load_vols`: remplacement des `except Exception` techniques par exceptions explicites (parsing date/heure, conversions, cache, lectures API) | OK |
| 2026-02-13 | Durcissement non fonctionnel `input_service`: exceptions explicites sur fallback de chargement vols + erreurs d’entrée | OK |
| 2026-02-13 | Durcissement non fonctionnel `core_scheduler`: migration des `print` runtime vers logging homogène + capture explicite des erreurs d’écriture stats | OK |
| 2026-02-13 | Renforcement tests `input_service` (fallback `load_and_normalize` + levée `InputLoadError` quand tous les chemins échouent) | OK |
| 2026-02-13 | Validation globale suite de tests (`269 passed, 1 skipped`) + audit régénéré (`270 tests collectés`, `loaders/*` sortis des hotspots `except Exception`, `core_scheduler` sorti des hotspots `print`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `ui_simulation`: remplacement des `except Exception` techniques (parsing/tri/export/ouverture fichier) par exceptions explicites | OK |
| 2026-02-13 | Durcissement non fonctionnel `ui_shipments_update_helpers`: remplacement des `except Exception` techniques (queue apply, parsing BE/date, lecture export, ouverture OS, PDF) par exceptions explicites | OK |
| 2026-02-13 | Durcissement non fonctionnel `ui_inputs`: exceptions explicites sur chargements/fallbacks API/cache/refresh + traitement dédié `InputLoadError` | OK |
| 2026-02-13 | Renforcement tests `ui_inputs` (`tests/test_ui_inputs_helpers.py`: upload limits, mtime fallback, copy/overwrite TMP, erreurs de chargement) | OK |
| 2026-02-13 | Validation globale suite de tests (`275 passed, 1 skipped`) + audit régénéré (`276 tests collectés`, `ui_inputs/ui_simulation/ui_shipments_update_helpers` sortis des hotspots `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `planning_exports_service`: remplacement des `except Exception` techniques (lecture preview/xlsx, parsing versions, mtime) par exceptions explicites | OK |
| 2026-02-13 | Durcissement non fonctionnel `ui_logs`: remplacement des `except Exception` techniques (I/O logs, sync OneDrive, rerun fallback) par exceptions explicites | OK |
| 2026-02-13 | Durcissement non fonctionnel `ui_stats`: remplacement des `except Exception` techniques (parsing semaine/version, fallback config paths, parsing heures) par exceptions explicites | OK |
| 2026-02-13 | Renforcement tests `ui_logs` / `ui_stats` (`tests/test_ui_logs_helpers.py`, `tests/test_ui_stats_helpers.py`) | OK |
| 2026-02-13 | Validation globale suite de tests (`279 passed, 2 skipped`) + audit régénéré (`280 tests collectés`, `ui_logs/planning_exports_service/ui_stats` sortis des hotspots `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `airfrance_api`: remplacement des `except Exception` techniques (imports optionnels, lecture .env, parsing config/secret) par exceptions explicites | OK |
| 2026-02-13 | Durcissement non fonctionnel `load_vols_api`: remplacement des `except Exception` techniques (parsing dates, fallbacks logger/excel/openpyxl, copie onglet API) par exceptions explicites | OK |
| 2026-02-13 | Renforcement tests `airfrance_api` / `load_vols_api` (fallback fichier .env absent, fallback secrets Streamlit, erreur loader BE) | OK |
| 2026-02-13 | Validation globale suite de tests (`282 passed, 2 skipped`) + audit régénéré (`283 tests collectés`, `airfrance_api/load_vols_api` sortis des hotspots `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `ui_week_data`: remplacement des `except Exception` techniques + migration des `print` debug vers logging structuré | OK |
| 2026-02-13 | Durcissement non fonctionnel `scheduler/format_rules`: remplacement des `except Exception` techniques (coercions date/numéro BE/vol) par exceptions explicites | OK |
| 2026-02-13 | Durcissement non fonctionnel `excel_automation`: remplacement des `except Exception` techniques par classes d’erreurs ciblées (incluant erreurs COM Windows) | OK |
| 2026-02-13 | Renforcement tests `ui_week_data` / `format_rules` / `excel_automation` (`tests/test_ui_week_data_core.py`, `tests/test_format_rules.py`, `tests/test_excel_automation.py`) | OK |
| 2026-02-13 | Validation globale suite de tests (`293 passed, 2 skipped`) + audit régénéré (`294 tests collectés`, `ui_week_data/format_rules/excel_automation` sortis des hotspots `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `asf_app/state`: migration `print` vers logger + exceptions explicites sur cache/session context | OK |
| 2026-02-13 | Durcissement non fonctionnel `asf_app/ui/ui_update`: exceptions explicites sur parsing/date/CSV + logs debug structurés | OK |
| 2026-02-13 | Durcissement non fonctionnel `scheduler/be_manager`: exceptions explicites sur coercitions numériques et aperçu debug | OK |
| 2026-02-13 | Renforcement tests `state` / `be_manager` (`tests/test_state_paths.py`, `tests/test_be_manager.py`) | OK |
| 2026-02-13 | Validation globale suite de tests (`296 passed, 2 skipped`) + audit régénéré (`297 tests collectés`, `state/ui_update/be_manager` sortis des hotspots `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `ui_params` / `ui_communication`: remplacement des `except Exception` techniques par exceptions explicites + logs structurés | OK |
| 2026-02-13 | Durcissement non fonctionnel `ui_communication/outlook` + handlers email destination/expéditeur: migration des `print` vers logger homogène | OK |
| 2026-02-13 | Renforcement tests ciblés (`tests/test_ui_params_helpers.py`, `tests/test_ui_communication_core.py`, `tests/test_outlook_helpers.py`) | OK |
| 2026-02-13 | Validation globale suite de tests (`308 passed, 2 skipped`) + audit régénéré (`309 tests collectés`, `ui_params/ui_communication/outlook` sortis des hotspots `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `ui_manual` / `config/settings`: exceptions explicites sur écriture Excel, parsing heures et coercitions numériques | OK |
| 2026-02-13 | Renforcement tests ciblés (`tests/test_ui_manual_helpers.py`, `tests/test_settings_helpers.py`) | OK |
| 2026-02-13 | Validation globale suite de tests (`314 passed, 2 skipped`) + audit régénéré (`315 tests collectés`, `ui_manual/settings` sortis des hotspots `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `load_benevoles` / `universal_loader` / `ui_notifications` / `files_service`: exceptions explicites sur cache/import/lecture Excel/notifications UI | OK |
| 2026-02-13 | Renforcement tests ciblés (`tests/test_loaders.py`, `tests/test_universal_loader.py`, `tests/test_files_service.py`, `tests/test_ui_notifications_helpers.py`) | OK |
| 2026-02-13 | Validation globale suite de tests (`318 passed, 2 skipped`) + audit régénéré (`319 tests collectés`, modules intermédiaires sortis des hotspots `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `session_context` / `load_params`: exceptions explicites sur téléchargement OneDrive, sync state et clear des caches Param* | OK |
| 2026-02-13 | Renforcement tests ciblés (`tests/test_session_context.py`, `tests/test_load_params_helpers.py`) | OK |
| 2026-02-13 | Validation globale suite de tests (`320 passed, 2 skipped`) + audit régénéré (`321 tests collectés`, `session_context/load_params` sortis des hotspots `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel “occurrences isolées” (`ui_shipments_update`, `email_defaults`, `runtime`, `stats_*`, `whatsapp_handler`, `onedrive_graph`, utilitaires `ui_helpers`/`identifiers`/`cache_utils`/`export_pdf`) | OK |
| 2026-02-13 | Renforcement tests ciblés (`tests/test_cache_utils_helpers.py`, `tests/test_runtime_helpers.py`, `tests/test_stats_processor_helpers.py`, `tests/test_stats_loader_helpers.py`, `tests/test_ui_helpers.py`, mises à jour `tests/test_identifiers.py`, `tests/test_whatsapp_handler.py`, `tests/test_graph_helpers.py`) | OK |
| 2026-02-13 | Validation globale suite de tests (`327 passed, 5 skipped`) + audit régénéré (`329 tests collectés`, plus que 6 fichiers avec `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `export_service` / `config_paths` / `ui_week_data_helpers` / `be_placement_service`: exceptions explicites sur export PDF/Excel, I/O TMP et parsing de secours | OK |
| 2026-02-13 | Renforcement tests ciblés (`tests/test_export_service_helpers.py`, `tests/test_config_paths.py`, `tests/test_ui_week_data_helpers.py`, `tests/test_be_placement_service.py`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `solver_ortools` / `solver_ortools_v3`: remplacement des `except Exception` et migration des `print` runtime vers logger | OK |
| 2026-02-13 | Renforcement tests solveur (`tests/test_solver_router.py`, `tests/test_solver_v3_strict_capacity.py`, `tests/test_core_scheduler.py`, `tests/test_data_sources.py`) | OK |
| 2026-02-13 | Validation globale suite de tests (`332 passed, 5 skipped`) + audit régénéré (`334 tests collectés`, plus aucun hotspot `except Exception`) | OK |
| 2026-02-13 | Durcissement non fonctionnel `audit_comm_planning`: migration complète des `print` vers logger structuré | OK |
| 2026-02-13 | Re-validation globale (`332 passed, 5 skipped`) + audit régénéré (`334 tests collectés`, plus aucun hotspot `except Exception` ni `print`) | OK |
| 2026-02-13 | Refactor structurel `solver_ortools` / `solver_ortools_v3`: extraction d’un noyau partagé dans `scheduler/solver_ortools_common.py` + wrappers V2/V3 (capacités V3 conservées) | OK |
| 2026-02-13 | Migration `scheduler/config_paths`: `prepare_paths` pilotable par `RuntimePaths`, propagation runtime sur helpers Graph, cache client Graph keyé par snapshot runtime | OK |
| 2026-02-13 | Renforcement tests ciblés (`tests/test_config_paths.py` + tests solveur), dont nouveaux cas sur `prepare_paths(runtime=...)` et cache Graph runtime-aware | OK |
| 2026-02-13 | Validation globale suite de tests (`334 passed, 5 skipped`) + collecte (`336`) + audit régénéré | OK |
| 2026-02-13 | Démarrage P2 outillage: ajout `.pre-commit-config.yaml` (hooks en `manual`), `.ruff.toml`, `mypy.ini`, `requirements-dev.txt` | OK |
| 2026-02-13 | CI non bloquante qualité: ajout job `quality_non_blocking` dans `.github/workflows/build.yml` | OK |
| 2026-02-13 | Hygiène dépôt: artefacts runtime retirés de l’index Git (`Planning.xlsx`, `Bilan.xlsx`, `engine_run_stats.json`, `test_api/export_vols.xlsx`) et ignorés | OK |
| 2026-02-13 | Validation bootstrap P2: installation `requirements-dev.txt` + exécution `pre-commit --hook-stage manual` (résultat attendu non bloquant: dette ruff/mypy visible) | OK |
| 2026-02-13 | Re-validation non régression métier (`334 passed, 5 skipped`) + audit régénéré (artefacts runtime suivis supprimés) | OK |
| 2026-02-13 | Résorption dette outillage P2: corrections `ruff` (imports/style), alignements typage sûrs (`mypy`) et harmonisation annotations Path/str/object sur modules service/UI/solver | OK |
| 2026-02-13 | Correctif de compatibilité tests: restauration de l’attribut module `loaders.load_vols.VOLS_SRC` (monkeypatch fixtures) | OK |
| 2026-02-13 | Validation qualité complète: `ruff` OK, `mypy` OK (`100` fichiers), `pre-commit --hook-stage manual` OK | OK |
| 2026-02-13 | Re-validation non-régression métier (`334 passed, 5 skipped`) + audit régénéré (`tools/hardening_audit.py`) | OK |
| 2026-02-13 | Industrialisation outillage P2: ajout du runner qualité `tools/run_quality.py` (sélection auto `.venv`/interpréteur système) | OK |
| 2026-02-13 | Activation gate locale: `.pre-commit-config.yaml` migré vers stage `pre-commit` (conserve `manual`) | OK |
| 2026-02-13 | Activation gate CI bloquante: job `quality` (sans `continue-on-error`) et dépendance `build -> quality` dans `.github/workflows/build.yml` | OK |
| 2026-02-13 | Documentation outillage mise à jour (`README.md`) + plan ré-aligné (lots restants) | OK |
| 2026-02-13 | Correctif compatibilité hooks: passage des entrées pre-commit de `python` vers `python3` (environnement local/CI) | OK |
| 2026-02-13 | Validation finale outillage: `pre-commit run --all-files` (stage `pre-commit`) = OK (`ruff` + `mypy`) | OK |
| 2026-02-13 | Re-validation non-régression métier (`334 passed, 5 skipped`) + audit régénéré | OK |
| 2026-02-13 | Industrialisation sécurité progressive: ajout scanner maison `tools/scan_secrets.py` (fichiers trackés, règles ciblées, faibles faux positifs) | OK |
| 2026-02-13 | Intégration outillage: hook `secret-scan` ajouté dans `.pre-commit-config.yaml` (stage `manual`) | OK |
| 2026-02-13 | CI sécurité progressive: ajout job `security_non_blocking` dans `.github/workflows/build.yml` | OK |
| 2026-02-13 | Documentation/plan alignés (`README.md`, `HARDENING_ACTION_PLAN.md`) | OK |
| 2026-02-13 | Promotion sécurité P2: hook `secret-scan` activé sur stage `pre-commit` + conservation `manual` | OK |
| 2026-02-13 | Promotion sécurité P2: job CI `security_non_blocking` remplacé par gate bloquante `security` + dépendance `build -> [quality, security]` | OK |
| 2026-02-13 | Stabilisation P1 contrats solveur: ajout tests croisés V2/V3 (`tests/test_solver_contracts.py`) sur dataset figé + dry-run | OK |
| 2026-02-13 | Validation qualité post-promotion sécurité: `pre-commit run --all-files` = OK (`ruff` + `mypy` + `secret-scan`) | OK |
| 2026-02-13 | Validation solveur ciblée (`tests/test_solver_contracts.py`, `tests/test_solver_v3_strict_capacity.py`, `tests/test_solver_router.py`) | OK |
| 2026-02-13 | Re-validation non-régression complète (`336 passed, 5 skipped`) + collecte (`338`) + audit régénéré | OK |
| 2026-02-13 | Durcissement `mypy`: activation effective `warn_unused_ignores = True` + suppression des ignores obsolètes (`utils/excel_automation.py`, `asf_app/ui/ui_communication/outlook.py`, `asf_app/ui/ui_simulation.py`) | OK |
| 2026-02-13 | Validation qualité complète: `mypy` OK, `pre-commit --all-files` OK (`ruff` + `mypy` + `secret-scan`) | OK |
| 2026-02-13 | Re-validation non-régression complète (`342 passed, 5 skipped`) + collecte (`344`) + audit régénéré | OK |
| 2026-02-13 | Durcissement scan secrets P2: ajout d’une allowlist regex versionnée (`.secret-scan-allowlist`) + intégration dans `tools/scan_secrets.py` | OK |
| 2026-02-13 | Renforcement tests outillage sécurité (`tests/test_tools_quality_security.py`: chargement allowlist + suppression findings allowlistés) | OK |
| 2026-02-13 | Validation globale après lot allowlist: `pre-commit --all-files` OK (`ruff` + `mypy` + `secret-scan`) + `pytest -q` OK (`344 passed, 5 skipped`) | OK |
| 2026-02-13 | Collecte/régénération audit: `346` tests collectés + `tools/hardening_audit.py` relancé | OK |
| 2026-02-13 | Mesure de couverture locale complète (`pytest --cov=asf_app --cov=scheduler --cov=loaders --cov=utils`): `62%` (`6569/10589`, `coverage.xml` généré) | OK |
| 2026-02-13 | Passe globale post-couverture: priorisation des zones restantes (UI communication/stats/inputs, `planning_enrichment`, `load_vols_api`) | OK |
| 2026-02-13 | Lot couverture ciblé: ajout tests `planning_enrichment` (`tests/test_planning_enrichment.py`) + handlers emails (`tests/test_email_handlers.py`) + `pdf_attachments` (`tests/test_pdf_attachments.py`) | OK |
| 2026-02-13 | Lot outillage/hygiène: ajout `coverage`/`pytest-cov` dans `requirements-dev.txt` + ignore `.coverage`/`coverage.xml` + doc commande couverture (`README.md`) | OK |
| 2026-02-13 | Validation complète après lots: `pre-commit --all-files` OK + `pytest -q` OK (`357 passed`) + couverture `62.47%` (`6615/10589`) | OK |
| 2026-02-13 | Re-génération audit technique (`tools/hardening_audit.py`) après montée couverture/outillage | OK |
| 2026-02-13 | Lot couverture communication: ajout tests `email_destinations_handler` + `email_expediteurs_handler` (`tests/test_destination_expediteur_handlers.py`) | OK |
| 2026-02-13 | Lot couverture loader API: enrichissement `tests/test_load_vols_api.py` (routes multi-dest, persistance feuille API, copie vers TMP) | OK |
| 2026-02-13 | Durcissement non-fonctionnel `load_vols_api`: remplacement `DataFrame.applymap` déprécié par `where(pd.notna(...), \"\")` | OK |
| 2026-02-13 | Validation complète après lots: `pre-commit --all-files` OK + `pytest -q` OK (`368 passed`) + couverture `63.96%` (`6773/10589`) | OK |
| 2026-02-13 | Re-génération audit technique (`tools/hardening_audit.py`) après montée couverture communication/API | OK |
| 2026-02-13 | Lot couverture `onedrive_graph`: ajout tests client Graph (auth/device-flow, download/upload small+chunked, listing récursif, pagination) dans `tests/test_onedrive_graph_client.py` | OK |
| 2026-02-13 | Lot couverture helpers communication: ajout tests `_detect_week_year`, listing local/OneDrive dans `tests/test_ui_communication_core.py` | OK |
| 2026-02-13 | Validation complète après lots: `pre-commit --all-files` OK + `.venv pytest -q` OK (`383 passed`) + couverture `65.15%` (`6899/10589`) | OK |
| 2026-02-13 | Re-génération audit technique (`tools/hardening_audit.py`) après lot Graph/UI communication | OK |
| 2026-02-13 | Lot couverture UI communication (session/OneDrive): ajout tests sur `_load_session_planning_ui` et `_load_onedrive_planning_ui` (`tests/test_ui_communication_core.py`) | OK |
| 2026-02-13 | Validation complète après lots: `pre-commit --all-files` OK + `.venv pytest -q` OK (`387 passed`) + couverture `65.60%` (`6946/10589`) | OK |
| 2026-02-13 | Re-génération audit technique (`tools/hardening_audit.py`) après lot UI communication supplémentaire | OK |
| 2026-02-13 | Correctif métier vols multi-escales: `load_vols`/`load_vols_df` étendent chaque routing en destinations candidates (`CDG-SSG-DLA` => `CDG-SSG` + `CDG-DLA`) avec capacité par destination ParamDest | OK |
| 2026-02-13 | Correctif solveur V2/V3: contrainte d’exclusivité “un vol physique (date+heure+numéro) ne peut servir qu’une destination” + tests de contrat dédiés | OK |
| 2026-02-13 | Validation ciblée post-correctif: `.venv pytest -q tests/test_loaders.py tests/test_solver_contracts.py tests/test_solver_v3_strict_capacity.py` (`13 passed`) | OK |
| 2026-02-13 | Règle métier conflit multi-escales: priorité forcée sur la 1ère destination du routing (`Route_Pos`) pour un même vol physique, avec fallback possible vers la destination suivante s’il n’y a pas de conflit BE | OK |
| 2026-02-13 | Renforcement tests métier multi-escales: cas NKC/CKY en conflit (priorité NKC), cas sans conflit (CKY seul), cas escale absente de ParamDest (SSG) mais destination finale DLA expédiée | OK |
| 2026-02-13 | Robustesse priorisation multi-escales: inférence de `Route_Pos` depuis `Routing` quand la colonne dédiée est absente (compat data sources externes) + test dédié | OK |
| 2026-02-13 | Validation ciblée post-renforcement: `.venv pytest -q tests/test_loaders.py tests/test_solver_contracts.py tests/test_solver_v3_strict_capacity.py` (`16 passed`) | OK |
| 2026-02-13 | Diagnostic solveur renforcé: ajout `vols_diagnostics` + métriques `nb_vols_sans_*_compatible` pour identifier les vols non utilisables (BE vs bénévoles) sans changer les règles métier | OK |
| 2026-02-13 | Validation ciblée diagnostic solveur: `.venv pytest -q tests/test_solver_contracts.py tests/test_solver_v3_strict_capacity.py tests/test_loaders.py` (`16 passed`) | OK |
| 2026-02-13 | Paramétrage runtime non-fonctionnel: `DUREE_MISSION_HEURES` et `MIN_HOURS_BETWEEN_FLIGHTS` lisibles via env (`ASF_DUREE_MISSION_HEURES`, `ASF_MIN_HOURS_BETWEEN_FLIGHTS`) avec valeurs par défaut inchangées | OK |
| 2026-02-13 | Documentation env mise à jour (`.env.example`) + tests dédiés config runtime (`tests/test_config_runtime_values.py`) | OK |
| 2026-02-13 | Re-baseline complète du plan: audit technique régénéré (`tools/hardening_audit.py`), collecte tests (`396`) et couverture locale (`401 passed`, `67%`, `coverage.xml`) | OK |
| 2026-02-13 | Passe qualité/sécurité globale: `ruff` KO (2 `I001`), `mypy` KO (6 erreurs `ui_simulation`), `scan_secrets` KO (6 faux positifs tests outillage) | À traiter en P0 |
| 2026-02-13 | Ajustement du phasage: priorité P0 sur restauration des gates qualité/sécurité + hygiène dépôt, puis P1 couverture ciblée UI/communication/stats et stabilisation solveur | Plan révisé |
| 2026-02-13 | P0 qualité: correction import-order solver (`solver_ortools.py`, `solver_ortools_v3.py`) + validation `ruff` (`All checks passed`) | OK |
| 2026-02-13 | P0 typage: correction régression `mypy` dans `ui_simulation` (conversions numériques + typage du contexte de raisons) | OK |
| 2026-02-13 | P0 sécurité: ajout allowlist ciblée des faux positifs dans `tests/test_tools_quality_security.py` + `tools/scan_secrets.py` vert | OK |
| 2026-02-13 | P0 hygiène dépôt: retrait de l’index Git des artefacts runtime (`Bilan.xlsx`, `Planning.xlsx`, `engine_run_stats.json`, `test_api/export_vols.xlsx`) | OK |
| 2026-02-13 | Validation P0 complète: `ruff` OK, `mypy` OK, `secret-scan` OK, `.venv pytest -q` OK (`401 passed`), `pre-commit --all-files` OK | OK |
| 2026-02-13 | Audit régénéré après P0 (`tools/hardening_audit.py`) : artefacts runtime résiduels supprimés de la liste (reste `.vscode/settings.json`) | OK |
