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

## État courant (après actions)
- Tests: `206 passed, 1 skipped`
- Tests collectés: `207`

## Backlog priorisé
1. Audit technique exhaustif (complexité, dette, duplication, robustesse erreurs, sécurité).
2. Renforcement tests métier sur points critiques non couverts.
3. Simplifications internes à faible risque (refactor non-fonctionnel, factorisation).
4. Sécurisation des flux secrets/config et messages d'erreur.
5. Durcissement outillage qualité (CI, checks locaux, documentation d'exploitation).
6. Préparer les lots de refactor lourds (UI monolithique, export monolithique, solveur dupliqué) avec stratégie anti-régression.

## Constats d'audit (en cours)
- Très grosses unités à risque maintenance:
  - `asf_app/ui/ui_shipments_update.py::render_tab_shipments_update` (~543 lignes, après extractions partielles)
  - `asf_app/services/export_service.py::export_planning_excel` (~525 lignes, après extraction de helpers MAG CENTRAL)
  - `asf_app/ui/ui_simulation.py::render_tab_simulation` (~410 lignes, après extraction de helpers)
  - `asf_app/ui/ui_week_data.py::render_tab_week_data` (~350 lignes, après extraction des helpers de vues semaine)
- Modules volumineux:
  - `asf_app/ui/ui_shipments_update.py` (743 lignes, après extraction de helpers queue/notifs/session/sélection BE/vol-bénévole/dispo-BE/prefill/notifications/apply-batch + sélection semaine/version/aperçu)
  - `asf_app/ui/ui_shipments_update_helpers.py` (1139 lignes, helperization UI shipments)
  - `asf_app/ui/ui_simulation.py` (1058 lignes, helpers de logique manuelle extraits en module unique)
  - `scheduler/solver_ortools_v3.py` (1300 lignes)
  - `scheduler/solver_ortools.py` (1106 lignes)
- Gestion d'erreurs très large (`except Exception`) concentrée surtout dans:
  - `asf_app/services/export_service.py` (28 occurrences)
  - `asf_app/services/shipments_update_service.py` (14)
  - `utils/datetime_utils.py` (14)
- Duplication solver:
  - similarité `solver_ortools.py` ↔ `solver_ortools_v3.py`: ~0.8655
- Couverture structurelle (approximation imports tests):
  - modules prod détectés: 98
  - importés directement par tests: 47
  - non importés directement: 42 (majoritairement couche UI communication/statistiques)
- Hygiène dépôt:
  - `.env` sorti de l'index Git et `.env*` ignorés
  - artefacts suivis en Git à surveiller (ex: `Planning.xlsx`, `Bilan.xlsx`, `test_api/export_vols.xlsx`)
- Audit automatisable:
  - script: `tools/hardening_audit.py`
  - rapport généré: `HARDENING_AUDIT_REPORT.md`

## Journal d'actions
| Date/Heure | Action | Résultat |
|---|---|---|
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
