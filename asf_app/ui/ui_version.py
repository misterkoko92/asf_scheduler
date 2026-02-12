# asf_app/ui/ui_version.py
# -----------------------
# Historique synthétique des changements

import streamlit as st


def render_tab_version():
    st.title("🧾 Version")
    st.caption("Historique synthétique des évolutions majeures.")

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
