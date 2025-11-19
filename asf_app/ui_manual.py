# asf_app/ui_manual.py
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd

from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    PLANNING_BENEVOLES,
    VOLS,
    SHEET_PARAM_BENEV,
    SHEET_PARAM_DEST,
)


# ================================================================
# 🔧 UTILITAIRES
# ================================================================

def lire_excel(path, sheet, **kwargs):
    """
    Lecture Excel sécurisée.
    """
    try:
        return pd.read_excel(path, sheet_name=sheet, **kwargs)
    except Exception as e:
        st.error(f"Erreur lecture de la feuille '{sheet}' dans '{path}' : {e}")
        return None


# ================================================================
# ONGLET AJOUTS MANUELS
# ================================================================

def render_tab_manual():
    st.header("➕ Ajouts manuels")

    # On utilise toujours les chemins de la session (pour respecter les uploads)
    path_tdb = st.session_state.paths["tdb"]
    path_benev = st.session_state.paths["benev"]
    path_vols = st.session_state.paths["vols"]

    # ======================================================================
    # 1️⃣ BÉNÉVOLES — FEUILLE SOURCE FILTRÉE PAR BÉNÉVOLE
    # ======================================================================
    with st.expander("👥 Ajouter / modifier des disponibilités bénévoles (Source)", expanded=False):

        # On charge ParamBenev pour récupérer la liste des bénévoles (Nom + Prénom)
        df_param = lire_excel(path_benev, SHEET_PARAM_BENEV, dtype=str)
        if df_param is None:
            st.stop()

        df_param = df_param.fillna("")

        # On suppose que la colonne BENEVOLE (col B) contient "NOM Prénom"
        if "BENEVOLE" in df_param.columns:
            bene_labels = sorted(df_param["BENEVOLE"].astype(str).unique())
        else:
            # Fallback : on prend la 2ème colonne comme BENEVOLE
            cols = list(df_param.columns)
            if len(cols) >= 2:
                bene_labels = sorted(df_param[cols[1]].astype(str).unique())
            else:
                st.error("Impossible d'identifier la colonne des bénévoles dans ParamBenev.")
                bene_labels = []

        bene_sel = st.selectbox(
            "Choisir un bénévole (Nom + Prénom)",
            bene_labels,
            index=None,
            placeholder="Tapez un nom…",
            key="manual_bene_select",
        )

        if not bene_sel:
            st.info("Sélectionnez un bénévole pour afficher/éditer ses lignes dans la feuille 'Source'.")
        else:
            # Lecture de la feuille Source
            # Les headers sont en ligne 4 -> header=3
            df_source_full = lire_excel(path_benev, "Source", header=3)
            if df_source_full is None:
                st.stop()

            df_source_full = df_source_full.fillna("")

            # On essaie de trouver la colonne du bénévole dans Source
            # Si une colonne s'appelle exactement "BENEVOLE", on la prend.
            if "BENEVOLE" in df_source_full.columns:
                col_bene_source = "BENEVOLE"
            else:
                # Fallback : on prend la 2ème colonne (B) comme libellé bénévole
                cols_src = list(df_source_full.columns)
                if len(cols_src) >= 2:
                    col_bene_source = cols_src[1]
                else:
                    st.error("Impossible d'identifier la colonne bénévole dans Source.")
                    st.stop()

            mask = df_source_full[col_bene_source].astype(str) == str(bene_sel)
            df_filtered = df_source_full.loc[mask].copy()

            if df_filtered.empty:
                st.warning(f"Aucune ligne trouvée dans 'Source' pour : {bene_sel}")
            else:
                st.caption(f"{len(df_filtered)} ligne(s) affichée(s) pour **{bene_sel}** dans la feuille 'Source'.")

                # On édite directement ces lignes
                edited = st.data_editor(
                    df_filtered,
                    num_rows="dynamic",
                    width="stretch",
                    key=f"editor_source_{bene_sel}",
                )

                if st.button("💾 Enregistrer les modifications dans 'Source'", key=f"save_source_{bene_sel}"):
                    # On réécrit uniquement les lignes de ce bénévole
                    df_new = df_source_full.copy()
                    # On force les index à correspondre
                    edited = edited.copy()
                    edited.index = df_filtered.index
                    df_new.loc[edited.index] = edited

                    try:
                        with pd.ExcelWriter(path_benev, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
                            df_new.to_excel(w, sheet_name="Source", index=False)
                        st.success(f"Feuille 'Source' mise à jour pour {bene_sel}.")
                    except Exception as e:
                        st.error(f"Erreur lors de l'écriture dans 'Source' : {e}")

    # ======================================================================
    # 2️⃣ VOLS — FEUILLE Vols MODIFIABLE + CONTRÔLE DESTINATIONS
    # ======================================================================
    with st.expander("✈️ Ajouter / modifier des vols (Vols)", expanded=False):

        # Lecture de la feuille Vols
        df_vols = lire_excel(path_vols, "Vols")
        if df_vols is None:
            st.stop()

        df_vols = df_vols.fillna("")

        # Lecture ParamDest pour les villes valides
        df_paramdest = lire_excel(path_tdb, SHEET_PARAM_DEST, dtype=str)
        if df_paramdest is not None:
            df_paramdest = df_paramdest.fillna("")
            # On prend la colonne Ville = col B
            if "Ville" in df_paramdest.columns:
                col_ville = "Ville"
            else:
                # Fallback : 2ème colonne
                cols_pd = list(df_paramdest.columns)
                col_ville = cols_pd[1] if len(cols_pd) >= 2 else cols_pd[0]

            destinations_valides = sorted(df_paramdest[col_ville].astype(str).unique())
        else:
            destinations_valides = []

        if destinations_valides:
            st.caption(
                "Villes connues (ParamDest, colonne Ville) : " +
                ", ".join(destinations_valides[:20]) +
                ("…" if len(destinations_valides) > 20 else "")
            )
        else:
            st.warning("Impossible de charger les villes depuis ParamDest. Vérifiez la feuille ParamDest.")

        # Édition directe du tableau Vols
        st.write("Modifiez directement le tableau ci-dessous (colonne A = ville destination).")
        edited_vols = st.data_editor(
            df_vols,
            num_rows="dynamic",
            width="stretch",
            key="editor_vols",
        )

        st.markdown(
            "_Rappel format attendu :_ "
            "`PVOL_FK_DESTINATION` = ville (ex: ABIDJAN), "
            "`PVOL_DATE` = 2025-11-23 00:00:00, "
            "`PVOL_HEURE` = 09:40:00, "
            "`PVOL_ROUTE_API` = [CDG,TNR] etc."
        )
        st.markdown(
            "_Pour les routings : respecter ce format sans espaces superflus, "
            "par ex. `[CDG,NSI,NIM]`._"
        )

        if st.button("💾 Enregistrer les vols modifiés", key="save_vols"):
            # Sauvegarde du DataFrame
            try:
                with pd.ExcelWriter(path_vols, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
                    edited_vols.to_excel(w, sheet_name="Vols", index=False)
                st.success("Feuille 'Vols' mise à jour.")
            except Exception as e:
                st.error(f"Erreur lors de l'écriture dans Vols.xlsx : {e}")
                st.stop()

            # Contrôle des destinations inconnues
            if len(edited_vols.columns) > 0:
                if "PVOL_FK_DESTINATION" in edited_vols.columns:
                    col_dest = "PVOL_FK_DESTINATION"
                else:
                    # Fallback : 1ère colonne
                    col_dest = edited_vols.columns[0]

                current_dest = (
                    edited_vols[col_dest]
                    .astype(str)
                    .str.strip()
                    .replace({"": pd.NA})
                    .dropna()
                    .unique()
                    .tolist()
                )

                if destinations_valides:
                    set_valid = set(d.strip() for d in destinations_valides if d.strip())
                    unknown = sorted(
                        d for d in current_dest
                        if d and d.strip() not in set_valid
                    )
                    if unknown:
                        st.warning(
                            "⚠️ Les destinations suivantes ne figurent pas dans ParamDest (colonne Ville) : "
                            + ", ".join(unknown)
                        )
                        st.info(
                            "Allez dans l’onglet **⚙️ Paramètres** puis la section **ParamDest** "
                            "pour les créer ou corriger."
                        )
                else:
                    st.info("Destinations non vérifiées car ParamDest n’a pas pu être chargé.")
