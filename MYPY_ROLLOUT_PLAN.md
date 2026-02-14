# Mypy Rollout Plan

## Objectif
Etendre progressivement `check_untyped_defs = True` package par package, sans instabilite CI.

## Regle de progression
Un package passe a l'etape suivante seulement si:
- `python tools/run_quality.py mypy` est vert sur `main`
- la suite `pytest -q` est verte
- aucun contournement fragile (`type: ignore` inutile) n'est ajoute

## Etat Courant
- Validation courante (2026-02-14): `mypy` vert (`Success: no issues found in 101 source files`).
Deja actives:
- `asf_app.ui.ui_stats.stats_processor`
- `asf_app.ui.ui_communication.whatsapp_handler`
- `asf_app.ui.ui_logs`
- `asf_app.ui.ui_manual`
- `asf_app.config.email_defaults`
- `asf_app.ui.email_defaults`
- `asf_app.ui.ui_planning.state_planning`

## Vague 1 (faible risque)
- `asf_app.config.runtime`
- `asf_app.config.session_context`
- `asf_app.services.params_service`
- `utils.logging_utils`

## Vague 2 (risque moyen)
- `scheduler.planning_views`
- `scheduler.models`
- `loaders.load_benevoles`
- `asf_app.services.input_service`

## Vague 3 (risque eleve, preparer refactor avant)
- `asf_app.ui.ui_inputs`
- `asf_app.ui.ui_params`
- `asf_app.ui.ui_simulation`
- `asf_app.ui.ui_communication.ui_communication`
- `scheduler.solver_ortools*`

## Processus par package
1. Activer `check_untyped_defs = True` dans `mypy.ini`.
2. Corriger les erreurs locales sans modifier le metier.
3. Ajouter/adapter des tests si necessaire.
4. Valider `ruff`, `mypy`, `pytest`.
5. Noter le lot dans `HARDENING_ACTION_PLAN.md`.
