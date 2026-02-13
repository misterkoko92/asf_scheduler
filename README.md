# ASF Scheduler — Moteur Automatisé de Planification MAB

ASF Scheduler est une application **Streamlit** conçue pour automatiser
le planning hebdomadaire de la **Messagerie Médicale & Fret Humanitaire** 
d’Aviation Sans Frontières.

Il combine :
- les expéditions (BE) du Magasin Central / Tableau de Bord
- les disponibilités bénévoles
- les vols Air France / partenaires
- les règles métiers ASF (fenêtres horaires, types BE, équivalences HF…)
- le placement intelligent des colis par destination
- l’affectation optimale des bénévoles par vol
- la génération du Planning.xlsx et du Bilan.xlsx

---

## 🚀 Fonctionnalités principales

- Import automatique des BE, vols et disponibilités
- Nettoyage, normalisation et consolidation des données
- Application des règles ASF :
  - statuts BE (P, X, D…)
  - priorités par type
  - équivalences colis → HF
  - règles destination / routing
  - capacité vol physique et capacité bénévole dynamique
- Placement intelligent des colis par destination et par vol (OR-Tools)
- Affectation optimale des bénévoles (fenêtre horaire + charge)
- Gestion multi-escales robuste :
  - un vol multi-stop expose ses escales comme destinations candidates
  - un vol physique (même date/heure/numéro) ne peut servir qu’une destination
  - en cas de conflit, la première destination du routing est prioritaire
- Génération Excel (depuis le planning simulé OR-Tools) :
  - planning complet
  - bilan expéditions
- Bilans enrichis en simulation :
  - bénévoles (`Nb_Dispo`, `Nb_Jours_Affectes`, `Nb_Vols_Affectes`, `Nb_BE_Affectes`)
  - expéditions (partants + non partants avec motif métier)
  - destination (`Nb_Vols_Existant`, `Nb_Vols_Utilises`)
- Interface Streamlit complète (OR-Tools uniquement)
- Onglet Communication : génération des messages depuis le planning de session ou un planning Excel OneDrive (feuille "Export planning")

---

## 📦 Structure du projet

- `asf_app/` : UI Streamlit (données semaine, planning OR-Tools, communication, mises à jour expéditions, statistiques…)
- `scheduler/` : moteur métier (règles, calcul de priorités, affectation vols/bénévoles, génération planning OR-Tools)
- `loaders/` : chargement / normalisation des sources Excel
- `data_test/` : jeux de données d’exemple

---

## 🧰 Prérequis

- Python 3.13 (recommandé)
- macOS ou Windows (usage Streamlit)

---

## ⚙️ Installation locale

```bash
git clone https://github.com/misterkoko92/asf_scheduler.git
cd asf_scheduler/new_repo
python3 -m venv .venv
source .venv/bin/activate      # sous Windows : .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## ▶️ Lancer l’app en local

```bash
cd asf_scheduler/new_repo
source .venv/bin/activate
python -m streamlit run app.py  # ouvre http://localhost:8501
```

Les chemins des fichiers Excel (Tableau de Bord, Planning, Param) sont configurés dans `scheduler/config_paths.py`. Assure‑toi que les fichiers OneDrive sont synchronisés localement.

Le chargement des sources est **fail-fast** : si un fichier source est introuvable, l’UI affiche l’erreur et stoppe la session.
La génération du planning se fait via l’onglet **Planning V2 (OR‑Tools)**.

Dans l’onglet simulation OR-Tools, les 2 modes ont des objectifs distincts :
- `Priorité Colis` : maximise les colis puis minimise le nombre de bénévoles affectés.
- `Priorité Bénévole` : maximise les colis puis maximise le nombre de bénévoles mobilisés.

Variables d’environnement utiles (chemins) :
- `ASF_ONEDRIVE_ROOT` : surcharge la racine OneDrive utilisée par l’app.
- `ASF_LISTES_COLISAGE_DIR` : surcharge le dossier des PDF “Listes de colisage” (pièces jointes des mails Destination/Expéditeur).

Variables d’environnement Air France API :
- `AF_API_KEY` : clé API Air France/KLM.
- `AF_MAX_CALLS_PER_DAY` : garde-fou local du nombre d’appels quotidiens (défaut `100`).
- `AF_MIN_DELAY_SECONDS` : délai mini entre deux appels API (défaut `1.1`).
- `AF_TIME_ORIGIN_TYPE` : référence temporelle des vols (`S`, `M`, `I`, `P`, défaut `P`).

Initialisation rapide :
```bash
cp .env.example .env
# puis renseigner AF_API_KEY dans .env
```

---

## 🔌 Sources de données (connecteurs API)

Par défaut, le moteur utilise les fichiers Excel locaux. Une couche `DataSource` permet
maintenant de se brancher aux APIs `asf-wms` (expéditions) et `asf-benev` (bénévoles).

Variables d’environnement supportées :
- `ASF_DATA_SOURCE=excel|composite|asf-wms|asf-benev`
- `ASF_WMS_ENABLE=1` / `ASF_BENEV_ENABLE=1`
- `ASF_WMS_API_URL` (ex: `https://wms.example.org/api/v1`)
- `ASF_WMS_API_KEY`
- `ASF_WMS_API_TIMEOUT` (optionnel, secondes)
- `ASF_BENEV_API_URL` (ex: `https://benev.example.org/api`)
- `ASF_BENEV_API_KEY` ou `ASF_BENEV_API_TOKEN`
- `ASF_BENEV_API_TIMEOUT` (optionnel, secondes)
- `ASF_BENEV_API_START` / `ASF_BENEV_API_END` (optionnel, filtre des disponibilités)

Mode recommandé :
- `ASF_DATA_SOURCE=composite` pour garder les vols via Excel, et lire les expéditions
  depuis `asf-wms` + les bénévoles depuis `asf-benev`.

## ☁️ Mode en ligne (Streamlit Cloud + OneDrive)

Ce mode utilise Microsoft Graph (auth déléguée) pour lire/écrire les fichiers OneDrive.

Variables d’environnement :
- `ASF_ONEDRIVE_MODE=graph`
- `ASF_GRAPH_CLIENT_ID` / `ASF_GRAPH_TENANT_ID`
- `ASF_GRAPH_SCOPES` (optionnel, défaut: `User.Read,Files.ReadWrite,offline_access`)

Chemins OneDrive (relatifs à la racine) configurables dans `scheduler/config_paths.py`
ou via ENV :
- `ASF_TDB_REMOTE_PATH`
- `ASF_BENEV_REMOTE_PATH`
- `ASF_VOLS_REMOTE_PATH`
- `ASF_LISTES_COLISAGE_REMOTE_DIR`
- `ASF_OUTPUT_REMOTE_DIR_TEMPLATE` (ex: `Planning MAB/ASFmm PLANNING {year}`)

Dans l’onglet **Fichiers d’entrée**, cliquer “Se connecter à OneDrive” et suivre
le device code. Les écritures Excel sont ensuite synchronisées vers OneDrive.

### Configuration Streamlit Cloud (secrets.toml)

1) Dans Streamlit Cloud → **Settings** → **Secrets**, ajouter :

```toml
ASF_ONEDRIVE_MODE = "graph"
ASF_GRAPH_CLIENT_ID = "c5f50f33-872b-413e-bdac-e4bd4706aad9"
ASF_GRAPH_TENANT_ID = "de5a5df7-c80f-491e-8c06-735e33880a8f"
# Optionnel si besoin de chemins personnalisés :
# ASF_TDB_REMOTE_PATH = "Hélida/TABLEAU DE BORD.xlsx"
# ASF_BENEV_REMOTE_PATH = "Planning Bénévoles/Planning BENEVOLE.xlsx"
# ASF_VOLS_REMOTE_PATH = "Planning MAB/Fichiers Source/aVols/Vols.xlsx"
# ASF_LISTES_COLISAGE_REMOTE_DIR = "8-Listes de colisage"
# ASF_OUTPUT_REMOTE_DIR_TEMPLATE = "Planning MAB/ASFmm PLANNING {year}"
```

2) Redéployer l’app (ou relancer).
3) Dans l’onglet **Fichiers d’entrée**, cliquer **Se connecter à OneDrive** et
   suivre le device code.

### FAQ Streamlit Cloud (OneDrive Graph)

**Le code d’appareil (device code) ne fonctionne pas :**
- Vérifier que `Allow public client flows` est bien activé dans l’app Azure.
- Vérifier `ASF_GRAPH_CLIENT_ID` / `ASF_GRAPH_TENANT_ID`.

**Erreur “insufficient privileges” :**
- Vérifier que les permissions Graph déléguées sont bien ajoutées : `User.Read`, `Files.ReadWrite`, `offline_access`.
- Si les fichiers sont dans un site SharePoint/Teams, ajouter `Sites.ReadWrite.All`.

**Les fichiers ne se chargent pas :**
- Vérifier les chemins OneDrive (variables `ASF_*_REMOTE_PATH`).
- Tester avec un chemin simple (ex: `8-Listes de colisage`) pour valider l’accès.

**Je veux forcer une reconnexion :**
- Relancer l’app (le cache token est recréé automatiquement).

### Troubleshooting logs (Streamlit Cloud)

Quand un chargement échoue :
- Ouvrir l’app Streamlit Cloud → **Manage app** → **Logs**.
- Copier la dernière erreur complète (trace + message).
- Indiquer l’action déclenchée (ex: “Recharger TDB”, “Se connecter à OneDrive”).

## 🧪 Tests

```bash
cd asf_scheduler/new_repo
source .venv/bin/activate
python -m pytest
```

Snapshot qualité (2026-02-13):
- `514` tests passés
- `85%` de couverture sur le périmètre `asf_app + scheduler + utils`
- dashboard global (incluant `loaders`): voir `QUALITY_DASHBOARD.md`

## 🏭 Outillage Qualité (P2)

Installation outillage local :

```bash
cd asf_scheduler/new_repo
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Activer les hooks locaux au commit :

```bash
PRE_COMMIT_HOME=.tmp_asf/.pre-commit-cache pre-commit install
```

Exécution manuelle des checks :

```bash
PRE_COMMIT_HOME=.tmp_asf/.pre-commit-cache pre-commit run --all-files
```

Commandes directes équivalentes :

```bash
ruff check asf_app scheduler loaders utils tests --config .ruff.toml
mypy --config-file mypy.ini asf_app scheduler loaders utils
pytest -q --cov=asf_app --cov=scheduler --cov=loaders --cov=utils --cov-report=term-missing --cov-report=xml
ASF_COVERAGE_MIN=75 python tools/run_quality.py coverage
python tools/run_quality.py dashboard
python tools/run_security.py all
```

Notes :
- Les hooks `pre-commit` sont configurés sur les stages `pre-commit` et `manual`.
- La CI exécute ces checks dans un job dédié `quality` bloquant avant la matrice build.
- Le scan secrets est actif dans les hooks locaux (`pre-commit` et `manual`) :
  `PRE_COMMIT_HOME=.tmp_asf/.pre-commit-cache pre-commit run secret-scan --all-files`
- L’audit dépendances local (manuel) est disponible :
  `PRE_COMMIT_HOME=.tmp_asf/.pre-commit-cache pre-commit run dependency-audit --all-files`
  (si offline, le check est ignoré par défaut; forcer l'échec avec `ASF_FAIL_ON_OFFLINE_AUDIT=1`)
- Les faux positifs du scanner peuvent être neutralisés via `.secret-scan-allowlist` (regex explicites et tracées).
- La CI exécute aussi ce scan dans le job bloquant `security`.
- Le job CI `coverage` applique un seuil progressif (`COVERAGE_MIN`, défaut `75`) avant le build multi-OS.
- Le dashboard qualité hebdo se génère avec `python tools/quality_dashboard.py --refresh`.

Runbooks:
- `RUNBOOK_QUALITY.md` : exploitation qualité hebdomadaire / gestion incidents.
- `MYPY_ROLLOUT_PLAN.md` : trajectoire package-par-package pour `check_untyped_defs`.

## 💬 Support / contributions

Ouvert aux issues et PR sur le repo GitHub. Pense à joindre un extrait de log/trace et, si possible, un échantillon de données anonymisées.
