# asf_app/ui_planning.py
# -*- coding: utf-8 -*-

import io
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from scheduler.core_scheduler import Scheduler
from loaders.load_shipments import load_shipments
from loaders.load_benevoles import load_benevoles
from scheduler import be_manager, volunteer_manager


def _ensure_session_keys():
    """S'assure que les clés de base existent dans session_state."""
    if "planning_df" not in st.session_state:
        st.session_state.planning_df = None
    if "bilan_df" not in st.session_state:
        st.session_state.bilan_df = None


def _run_scheduler():
    """Lance le moteur principal et stocke le résultat dans session_state."""
    scheduler = Scheduler()
    planning_df, bilan_df = scheduler.run()
    st.session_state.planning_df = planning_df
    st.session_state.bilan_df = bilan_df


def _load_unplanned_shipments(planning_df: pd.DataFrame):
    """
    Charge les BE filtrés par le moteur et retourne :
    - la liste complète des Shipments filtrés + triés
    - la liste des BE "non encore dans le planning"
    """
    all_be = load_shipments()
    all_be = be_manager.filter_shipments(all_be)
    all_be = be_manager.sort_shipments(all_be)

    already_planned = set()
    if planning_df is not None and not planning_df.empty and "BE_Numero" in planning_df.columns:
        already_planned = set(planning_df["BE_Numero"].astype(str).tolist())

    # BE filtrés par moteur et non encore dans le planning
    unplanned = [s for s in all_be if str(s.be_numero) not in already_planned]

    return all_be, unplanned


def _load_vols_df():
    """Charge le fichier Vols.xlsx présent dans st.session_state.paths['vols']."""
    path_vols = st.session_state.paths.get("vols")
    if not path_vols or not os.path.exists(path_vols):
        return None

    try:
        df_vols = pd.read_excel(path_vols, dtype=str).fillna("")
        return df_vols
    except Exception as e:
        st.error(f"❌ Erreur de lecture du fichier Vols : {e}")
        return None


def _load_volunteers():
    """Charge la liste des bénévoles via le moteur existant."""
    try:
        df = load_benevoles()
        param = volunteer_manager.load_param_benev()
        volunteers = volunteer_manager.build_volunteers(df, param)
        # Tri pour affichage
        volunteers = sorted(
            volunteers,
            key=lambda v: (str(getattr(v, "nom", "")), str(getattr(v, "prenom", "")))
        )
        return volunteers
    except Exception as e:
        st.error(f"❌ Erreur de chargement des bénévoles : {e}")
        return []


def render_tab_planning():
    """Rendu de l'onglet '📊 Planning'."""
    _ensure_session_keys()

    st.header("📊 Lancer le planning et ajuster")

    # ----------------------------------------------------------------------
    # LANCER LE PLANNING
    # ----------------------------------------------------------------------
    col_run, col_info = st.columns([1, 3])
    with col_run:
        if st.button("🚀 Lancer le planning"):
            with st.spinner("Calcul du planning en cours…"):
                _run_scheduler()
            st.success("✅ Planning généré ou mis à jour.")

    with col_info:
        if st.session_state.planning_df is not None and not st.session_state.planning_df.empty:
            nb_lignes = len(st.session_state.planning_df)
            st.info(f"Planning en mémoire : **{nb_lignes} lignes**.")
        else:
            st.info("Aucun planning en mémoire. Lance le moteur pour créer un planning.")

    st.markdown("---")

    planning_df = st.session_state.planning_df
    bilan_df = st.session_state.bilan_df

    # ----------------------------------------------------------------------
    # AFFICHAGE DU PLANNING + EXPORTS
    # ----------------------------------------------------------------------
    if planning_df is not None and not planning_df.empty:
        st.subheader("📋 Planning généré")

        st.dataframe(planning_df, use_container_width=True)

        col_export1, col_export2 = st.columns(2)
        with col_export1:
            buf_plan = io.BytesIO()
            planning_df.to_excel(buf_plan, index=False)
            buf_plan.seek(0)
            st.download_button(
                "⬇️ Télécharger Planning.xlsx",
                data=buf_plan,
                file_name="Planning.xlsx",
            )

        with col_export2:
            if bilan_df is not None and not bilan_df.empty:
                buf_bilan = io.BytesIO()
                bilan_df.to_excel(buf_bilan, index=False)
                buf_bilan.seek(0)
                st.download_button(
                    "⬇️ Télécharger Bilan.xlsx",
                    data=buf_bilan,
                    file_name="Bilan.xlsx",
                )

        st.markdown("---")

        # ------------------------------------------------------------------
        # AJOUT MANUEL D'UN BE
        # ------------------------------------------------------------------
        st.subheader("➕ Ajouter manuellement un BE au planning")

        # Charge les BE filtrés par le moteur et ceux non encore planifiés
        all_be, unplanned_be = _load_unplanned_shipments(planning_df)

        if not unplanned_be:
            st.info("✅ Tous les BE prêts sont déjà présents dans le planning.")
            return

        # Index des Shipments par N° BE (str)
        be_index = {str(s.be_numero): s for s in all_be}
        unplanned_be_nums = sorted({str(s.be_numero) for s in unplanned_be})

        # Charge les vols (DataFrame brut)
        df_vols = _load_vols_df()
        if df_vols is None or df_vols.empty:
            st.error("❌ Impossible de charger les vols. Vérifie le fichier Vols.xlsx dans l'onglet Fichiers d'entrée.")
            return

        # Préparation du planning existant pour calcul du remplissage par vol
        plan_for_load = planning_df.copy()
        if "Date_Vol" in plan_for_load.columns:
            plan_for_load["Date_Vol_obj"] = pd.to_datetime(
                plan_for_load["Date_Vol"], errors="coerce"
            ).dt.date
        else:
            plan_for_load["Date_Vol_obj"] = pd.NaT

        if "BE_Nb_Colis" in plan_for_load.columns:
            plan_for_load["BE_Nb_Colis_int"] = pd.to_numeric(
                plan_for_load["BE_Nb_Colis"], errors="coerce"
            ).fillna(0).astype(int)
        else:
            plan_for_load["BE_Nb_Colis_int"] = 0

        # Liste des bénévoles
        volunteers = _load_volunteers()
        benev_labels = [f"{getattr(v, 'nom', '')} {getattr(v, 'prenom', '')}".strip() for v in volunteers]

        # ------------------------- LAYOUT DU FORMULAIRE --------------------
        # Ligne 1 : N° BE / Destination / Nb Colis / Type de Colis
        col_be, col_dest, col_nb, col_type = st.columns([1.5, 1.5, 1, 1])

        with col_be:
            selected_be_num = st.selectbox(
                "N° BE (BE prêts non planifiés)",
                options=unplanned_be_nums,
                key="manual_be_num",
                help="Liste déroulante filtrée sur les BE prêts à expédier et non encore dans le planning. Tu peux taper pour filtrer."
            )

        # Récupère l'objet Shipment associé
        shipment = be_index.get(selected_be_num)

        if shipment is not None:
            dest_value = getattr(shipment, "dest", "")
            nb_colis_value = getattr(shipment, "nb_colis_physiques", 0)
            type_colis_value = getattr(
                shipment,
                "type_colis",
                getattr(shipment, "be_type", "")
            )
        else:
            dest_value = ""
            nb_colis_value = 0
            type_colis_value = ""

        with col_dest:
            st.text_input(
                "Destination",
                value=str(dest_value),
                disabled=True,
                key="manual_dest",
            )

        with col_nb:
            st.text_input(
                "Nb colis réels",
                value=str(nb_colis_value),
                disabled=True,
                key="manual_nb_colis",
            )

        with col_type:
            st.text_input(
                "Type de colis",
                value=str(type_colis_value),
                disabled=True,
                key="manual_type_colis",
            )

        # Si pas de destination associée au BE → pas la peine d'aller plus loin
        if not dest_value:
            st.warning("Impossible de déterminer la destination pour ce BE. Vérifie MAG CENTRAL.")
            return

        # ---------------- Ligne 2 : Date de vol / N° de vol / Heure de vol ----
        col_date, col_vol, col_heure = st.columns([1.5, 1.5, 1])

        # Filtre les vols pour la destination
        if "PVOL_FK_DESTINATION" in df_vols.columns:
            df_vols_dest = df_vols[df_vols["PVOL_FK_DESTINATION"] == str(dest_value)]
        else:
            df_vols_dest = pd.DataFrame()

        if df_vols_dest.empty:
            st.error(f"Aucun vol trouvé pour la destination {dest_value} dans Vols.xlsx.")
            return

        # Dates disponibles pour cette destination
        df_vols_dest = df_vols_dest.copy()
        df_vols_dest["DATE_OBJ"] = pd.to_datetime(
            df_vols_dest["PVOL_DATE"], errors="coerce"
        ).dt.date

        valid_dates = sorted(df_vols_dest["DATE_OBJ"].dropna().unique())
        date_labels = [d.strftime("%Y-%m-%d") for d in valid_dates]

        with col_date:
            if valid_dates:
                date_label_choice = st.selectbox(
                    "Date de vol",
                    options=date_labels,
                    key="manual_date_vol",
                    help="Seules les dates disposant d'au moins un vol pour cette destination sont proposées."
                )
                date_choice_obj = valid_dates[date_labels.index(date_label_choice)]
            else:
                date_choice_obj = None
                st.warning("Aucune date de vol valide trouvée pour cette destination.")

        # Filtre les vols à cette date pour cette destination
        if date_choice_obj:
            df_vols_date = df_vols_dest[df_vols_dest["DATE_OBJ"] == date_choice_obj]
        else:
            df_vols_date = pd.DataFrame()

        # Construction des options de vols avec notion de colis déjà affectés
        vol_labels = []
        vol_map_label_to_num = {}

        if not df_vols_date.empty:
            for _, row in df_vols_date.iterrows():
                vol_num = row.get("PVOL_NUMERO", "")
                # Calcul du remplissage déjà dans le planning
                mask = (
                    (plan_for_load.get("Destination", "") == str(dest_value))
                    & (plan_for_load.get("Vol", "") == str(vol_num))
                    & (plan_for_load["Date_Vol_obj"] == date_choice_obj)
                )
                nb_colis_sur_vol = int(plan_for_load.loc[mask, "BE_Nb_Colis_int"].sum())

                if nb_colis_sur_vol > 0:
                    label = f"{vol_num} — déjà affecté {nb_colis_sur_vol} colis"
                else:
                    label = f"{vol_num}"

                vol_labels.append(label)
                vol_map_label_to_num[label] = vol_num

        with col_vol:
            if vol_labels:
                selected_vol_label = st.selectbox(
                    "N° de vol",
                    options=vol_labels,
                    key="manual_vol_num",
                    help="Les vols déjà partiellement remplis sont indiqués."
                )
                selected_vol_num = vol_map_label_to_num[selected_vol_label]
            else:
                selected_vol_label = None
                selected_vol_num = None
                st.warning("Aucun vol trouvé pour cette date et cette destination.")

        # Heure de vol auto à partir du vol choisi
        with col_heure:
            if selected_vol_num:
                row_match = df_vols_date[df_vols_date["PVOL_NUMERO"] == selected_vol_num]
                if not row_match.empty:
                    heure_vol = row_match.iloc[0].get("PVOL_HEURE", "")
                else:
                    heure_vol = ""
            else:
                heure_vol = ""

            st.text_input(
                "Heure de vol",
                value=str(heure_vol),
                disabled=True,
                key="manual_heure_vol",
            )

        # ---------------- Ligne 3 : Bénévole(s) affecté(s) ---------------------
        st.markdown("")
        col_benev, _ = st.columns([2, 1])

        with col_benev:
            selected_benev_labels = st.multiselect(
                "Bénévole(s) affecté(s)",
                options=benev_labels,
                key="manual_benev_labels",
                help="Tape quelques lettres du nom (ex : 'ALB') pour filtrer. Tu peux en sélectionner plusieurs."
            )

        # ------------------------------------------------------------------
        # BOUTON D'AJOUT
        # ------------------------------------------------------------------
        if st.button("💾 Ajouter ce BE au planning", type="primary"):
            # Validations simples
            if shipment is None:
                st.error("BE inconnu. Impossible d'ajouter.")
                return
            if not date_choice_obj or not selected_vol_num:
                st.error("Tu dois choisir une date de vol et un numéro de vol.")
                return

            # Construction de la ligne à ajouter
            benevole_cell = " / ".join(selected_benev_labels) if selected_benev_labels else ""

            new_row = {
                "Date_Vol": date_choice_obj,
                "Heure_Vol": heure_vol,
                "Vol": selected_vol_num,
                "Destination": dest_value,
                "BE_Numero": selected_be_num,
                "BE_Nb_Colis": nb_colis_value,
                "BE_Nb_Equiv": nb_colis_value,  # simplification
                "Benevole": benevole_cell,
            }

            st.session_state.planning_df = pd.concat(
                [st.session_state.planning_df, pd.DataFrame([new_row])],
                ignore_index=True
            )

            st.success(f"✅ BE {selected_be_num} ajouté manuellement au planning.")

            # On force un léger ré-affichage
            st.experimental_rerun()

    else:
        st.info("⚠️ Aucun planning généré pour le moment. Clique sur 'Lancer le planning'.")
