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

