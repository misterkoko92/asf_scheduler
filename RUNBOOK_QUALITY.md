# Runbook Qualite

## Objectif
Maintenir des garde-fous techniques stables (lint, typage, tests, securite) sans casser le delivery.

## Etat de reference (2026-02-13)
- `pytest -q`: `514 passed`
- Couverture perimetre lot hardening (`asf_app + scheduler + utils`): `85%`
- Dashboard global (incluant `loaders`): `83.64%`
- Gates qualite: `ruff`, `mypy`, `coverage`, `secrets` = `pass`

## Frequence
- Quotidien (avant merge): checks locaux rapides.
- Hebdomadaire: snapshot qualite complet + mise a jour du dashboard.

## Routine Quotidienne
```bash
python tools/run_quality.py ruff
python tools/run_quality.py mypy
python tools/run_quality.py coverage
python tools/run_security.py secrets
```

## Routine Hebdomadaire
```bash
python tools/quality_dashboard.py --refresh
```

Fichiers mis a jour:
- `QUALITY_DASHBOARD.md`
- `QUALITY_DASHBOARD_HISTORY.csv`

## Lecture du Dashboard
- `Coverage total` doit rester >= `Coverage target`.
- `Quality Gates` doit etre `pass` sur `Ruff`, `Mypy`, `Coverage`, `Secrets`.
- `Lowest Coverage Modules` guide les prochains lots de tests.

## Gestion d'Incident Qualite
1. Identifier le gate en echec (`ruff`, `mypy`, `coverage`, `secrets`).
2. Corriger en priorite le code modifie par le lot courant.
3. Relancer le gate isole puis la suite complete.
4. Mettre a jour `HARDENING_ACTION_PLAN.md` avec cause et correctif.

## Ratchet Coverage
- Seuil CI courant: `75%`.
- Niveau observe: `83.64%` (dashboard global) / `85%` (perimetre hardening).
- Cible suivante: `80%` (CI) puis `85%` quand stable.
- Le ratchet se fait uniquement quand le niveau observe est durablement au-dessus de la cible.

## Liens
- `README.md` (commandes de reference)
- `MYPY_ROLLOUT_PLAN.md` (plan de montee en strict)
- `HARDENING_ACTION_PLAN.md` (journal des lots)
