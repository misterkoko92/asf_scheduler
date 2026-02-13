# asf_app/ui/ui_version.py
# -----------------------
# Historique synthétique des changements

import streamlit as st


def render_tab_version():
    st.title("🧾 Version")
    st.caption("Historique synthétique des évolutions majeures.")

    st.markdown("### 2026-02-13 — Stabilisation simulation & bilans")
    st.markdown(
        """
- Gestion multi-escales consolidée : un vol physique (même date/heure/numéro) est unique en affectation.
- Priorité en conflit multi-destinations : la **première destination du routing** est retenue.
- Affichage du **routing réel** conservé dans les vues planning et sélecteurs de vols.
- Déduplication des vols multi-escales dans les listes de sélection et vues hebdo.
- Bilan des bénévoles enrichi : `Nb_Dispo`, `Nb_Jours_Affectes`, `Nb_Vols_Affectes`, `Nb_BE_Affectes`.
- Bilan des expéditions enrichi : BE partants et non partants + raison métier de non-affectation.
- Bilan par destination enrichi : `Nb_Vols_Existant` et `Nb_Vols_Utilises`.
        """
    )

    st.markdown("### 2026-02-02 — V3 solver & capacités bénévoles")
    st.markdown(
        """
- Ajout d’un **solver V3** avec **capacité stricte par bénévole** (Max_Colis_Vol).
- Nouvelle colonne **MAX_COLIS_VOL** dans ParamBenev (Planning BENEVOLE).
- Support API `asf-benev.constraints.max_assigned_volunteer_flight`.
- Planning généré à partir de l’assignation BE → bénévole (plus de répartition greedy).
- **Switch V2/V3 visible** dans Paramètres → Paramoteur (défaut V3).
        """
    )
