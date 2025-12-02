# asf_app/ui/ui_communication/whatsapp_ui.py
# --------------------------------------------------------------------
# Interface Streamlit pour afficher les messages WhatsApp
# générés par whatsapp_handler.generate_whatsapp_messages(df_comm)
# --------------------------------------------------------------------

import streamlit as st

from asf_app.ui.ui_communication.whatsapp_handler import (
    generate_whatsapp_messages,
    open_whatsapp_for_benevole,
)
from asf_app.ui.ui_planning.state_planning import get_planning_state

def render_whatsapp_ui(df_comm):
    """
    UI WhatsApp dans l'onglet Communication.
    df_comm : tableau structuré par build_df_comm
    """

    st.subheader("💬 Messages WhatsApp")

    if df_comm is None or df_comm.empty:
        st.info("Aucune donnée disponible (df_comm vide).")
        return

    # Génération messages
    msgs = generate_whatsapp_messages(df_comm)

    if not msgs:
        st.warning("Aucun message WhatsApp à générer (aucun bénévole avec téléphone).")
        return

    st.success(f"{len(msgs)} message(s) généré(s).")

    # ---------------------------------------------------------------
    # Liste des bénévoles
    # ---------------------------------------------------------------
    for entry in msgs:
        bene = entry["benevole"]
        tel = entry["telephone"]
        msg = entry["message"]
        url = entry["url"]

        st.markdown(f"### 👤 {bene} — {tel}")

        # Message affiché
        with st.expander("Afficher le message"):
            st.text(msg)

        # Bouton ouverture WhatsApp
        if st.button(f"📲 Ouvrir WhatsApp → {bene}", key=f"wa_{tel}"):
            open_whatsapp_for_benevole(url)

        st.markdown("---")
