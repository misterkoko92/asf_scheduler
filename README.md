# ASF Scheduler — Moteur Automatisé de Planification MAB

ASF Scheduler est un moteur Python/Streamlit conçu pour automatiser
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
- Placement intelligent des colis par destination et par vol
- Affectation optimale des bénévoles (fenêtre horaire + charge)
- Génération Excel :
  - planning complet
  - bilan expéditions
- Interface Streamlit complète

---

## 📦 Structure du projet

- `asf_app/` : UI Streamlit (onglets planning, communication, mises à jour expéditions, statistiques…)
- `scheduler/` : moteur métier (règles, calcul de priorités, affectation vols/bénévoles, génération planning)
- `loaders/` : chargement / normalisation des sources Excel
- `data_test/` : jeux de données d’exemple
- `.github/workflows/build.yml` : pipeline PyInstaller (macOS + Windows) + publication automatique sur un tag

---

## 🧰 Prérequis

- Python 3.13 (recommandé)
- macOS ou Windows (pour l’exécutable, les deux artefacts sont générés)

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

---

## 🔌 Sources de données (préparation intégrations)

Par défaut, le moteur utilise les fichiers Excel locaux. Une couche `DataSource` est en place pour préparer l’intégration future de :
- `asf-wms` (BE / expéditions)
- `asf-benev` (disponibilités bénévoles)

Variables d’environnement supportées :
- `ASF_DATA_SOURCE=excel|composite|asf-wms|asf-benev`
- `ASF_WMS_ROOT` (défaut: `~/asf-wms`)
- `ASF_BENEV_ROOT` (défaut: `~/asf-benev`)
- `ASF_WMS_ENABLE=1` / `ASF_BENEV_ENABLE=1` pour activer les sources externes quand elles seront implémentées.

⚠️ Les connecteurs `asf-wms` / `asf-benev` sont volontairement des stubs pour l’instant : ils doivent être branchés sur les APIs ou exports locaux des projets concernés.

---

## 🧪 Tests

```bash
cd asf_scheduler/new_repo
source .venv/bin/activate
python -m pytest
```

---

## 📦 Builds PyInstaller & Releases

Le workflow GitHub Actions `build.yml` :
- s’exécute sur chaque push (branche `main`) et sur les tags `v*`,
- build un exécutable macOS et Windows (PyInstaller),
- sur un tag, attache automatiquement les artefacts à la release GitHub.

Pour publier une version :
```bash
cd asf_scheduler/new_repo
git tag v1.0.0
git push origin v1.0.0
```
La release GitHub est alors enrichie automatiquement des binaires (`ASF-Scheduler-macos-latest`, `ASF-Scheduler-windows-latest`).

---

## 💬 Support / contributions

Ouvert aux issues et PR sur le repo GitHub. Pense à joindre un extrait de log/trace et, si possible, un échantillon de données anonymisées.
