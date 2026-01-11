# asf_app/ui/ui_update.py
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
from pathlib import Path

import scheduler.config_paths as cp
from scheduler.config_paths import (
    TABLEAU_DE_BORD,
    SHEET_PARAM_BE,
    BASE_DIR,  # pour accéder à data/BE.csv
)

from asf_app.ui.ui_stats.ui_stats import (
    load_planning_xlsx,
    extract_week_version,
    filter_latest,
)

# ==== IMPORTS BE MOTEUR ======================================================
from loaders.universal_loader import load_and_normalize
from scheduler.column_map import column_map_param_be


# ============================================================================
# 🟦 ONGLET MISE À JOUR DU PLANNING
# ============================================================================

def render_tab_update():

    st.header("🔄 Mise à jour d’un planning validé")

    # ------------------------------------------------------------------
    # 1) Sélection SEMAINE ou FICHIER (tri du plus récent au plus ancien)
    # ------------------------------------------------------------------

    st.subheader("📆 Sélection du planning validé")

    if cp.is_graph_onedrive():
        items = cp.list_onedrive_files(
            "Planning MAB",
            recursive=True,
            suffixes=[".xls", ".xlsx", ".xlsm"],
        )
        remote_files = [
            i.get("path", "")
            for i in items
            if i.get("name", "").upper().startswith("ASFMM - PLANNING SEMAINE N°")
        ]
        if not remote_files:
            st.error("❌ Aucun planning trouvé dans OneDrive (Graph).")
            st.stop()

        def _filter_latest_remote(paths):
            latest = {}
            for p in paths:
                wk, ver = extract_week_version(Path(p).name)
                if wk is None:
                    continue
                if wk not in latest or ver > latest[wk][0]:
                    latest[wk] = (ver, p)
            return [x[1] for x in latest.values()]

        files = _filter_latest_remote(remote_files)
    else:
        # Dossier des plannings validés : par défaut dossier ASFmm (OneDrive),
        # fallback sur le dossier de sortie du moteur.
        planning_dir = cp.ASF_ONEDRIVE / "Planning MAB" / "ASFmm PLANNING 2025"
        if not planning_dir.exists():
            planning_dir = cp.OUTPUT_PLANNING_DIR

        # On travaille dans planning_dir, sur tous les formats Excel
        all_files = sorted(
            [
                f
                for f in planning_dir.glob("ASFmm - PLANNING SEMAINE N° *.xls*")
                if f.is_file()
            ],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        if not all_files:
            st.error(f"❌ Aucun planning trouvé dans :\n{planning_dir}")
            st.stop()

        # On garde uniquement la dernière version par semaine
        files = filter_latest(all_files)

    if not files:
        st.error("❌ Aucun planning validé trouvé (après filtrage par version).")
        st.stop()

    # ---- Sélecteur SEMAINE ----
    week_labels = []
    week_map = {}

    for f in files:
        name = Path(f).name if isinstance(f, str) else f.name
        wk, _ = extract_week_version(name)
        if wk is None:
            continue
        label = f"Semaine {wk:02d}"
        week_labels.append(label)
        week_map[label] = f

    week_labels = sorted(set(week_labels))

    if not week_labels:
        st.error("❌ Impossible d'extraire les numéros de semaine des fichiers.")
        st.stop()

    choice_week = st.selectbox("Par semaine :", week_labels)

    # ---- Sélecteur fichier brut ----
    file_map = {Path(f).name if isinstance(f, str) else f.name: f for f in files}
    choice_file = st.selectbox(
        "Ou sélectionner un fichier :",
        list(file_map.keys()),
    )

    # ---- Fichier retenu ----
    if choice_week and choice_week in week_map:
        planning_path = week_map[choice_week]
    else:
        planning_path = file_map.get(choice_file)

    if isinstance(planning_path, str):
        remote_path = planning_path
        local_path = cp.TMP_DIR / "onedrive_cache" / "planning_exports" / remote_path
        if not local_path.exists():
            cp.download_onedrive_file(remote_path, local_path, interactive=False)
        planning_path = local_path

    st.success(f"✔ Planning sélectionné : {Path(planning_path).name}")

    # ------------------------------------------------------------------
    # 2) Lecture du fichier XLSX / XLSM via loader hybride index-based
    # ------------------------------------------------------------------
    df_plan = load_planning_xlsx(planning_path)

    if df_plan is None or df_plan.empty:
        st.error("❌ Impossible de lire le planning (DataFrame vide).")
        st.stop()

    print("\n🐞 DEBUG UI_UPDATE — Planning chargé")
    print("Colonnes :", list(df_plan.columns))
    try:
        print(df_plan.head())
    except Exception:
        pass
    print("====================================\n")

    # ------------------------------------------------------------------
    # 3) BLOCS ACTIONS
    # ------------------------------------------------------------------
    st.markdown("## ➕✏️🗑️ Actions sur le planning")

    with st.expander("➕ Ajouter un BE"):
        render_block_add(df_plan)

    with st.expander("✏️ Modifier une mise à bord"):
        render_block_modify(df_plan)

    with st.expander("🗑️ Supprimer une mise à bord"):
        render_block_delete(df_plan)

    # ------------------------------------------------------------------
    # 4) Appliquer modifications
    # ------------------------------------------------------------------
    render_block_apply_changes(df_plan)

    # ------------------------------------------------------------------
    # 5) Aperçu planning anti-crash
    # ------------------------------------------------------------------
    st.divider()
    st.markdown("## 📋 Planning actuel")

    df_show = df_plan.copy()
    for col in df_show.columns:
        if "date" in col.lower():
            try:
                df_show[col] = pd.to_datetime(df_show[col], errors="coerce").astype(
                    str
                )
            except Exception:
                df_show[col] = df_show[col].astype(str)

    st.dataframe(df_show, width="stretch")


# ============================================================================
# 🟢 AJOUT — UTILISE data/BE.csv (moteur) AU LIEU DE planter sur ParamBE/'AUTRE'
# ============================================================================

def render_block_add(df_plan):

    st.markdown("## ➕ Ajouter une mise à bord")

    # On part de BE.csv généré par le moteur (CLI / Streamlit)
    be_csv = BASE_DIR / "data" / "BE.csv"

    if not be_csv.exists():
        st.error(
            f"❌ Fichier BE.csv introuvable : {be_csv}\n"
            "Lance au moins une fois le moteur pour générer ce fichier."
        )
        return

    try:
        df_be_raw = pd.read_csv(be_csv, dtype=object)
    except Exception as e:
        st.error(f"Erreur lecture BE.csv : {e}")
        return

    if df_be_raw.empty or "BE_NUMERO" not in df_be_raw.columns:
        st.error("BE.csv vide ou invalide (colonne BE_NUMERO manquante).")
        return

    # On ne garde que les BE planifiables si la colonne existe
    if "BE_STATUT" in df_be_raw.columns:
        mask_planif = df_be_raw["BE_STATUT"].astype(str) == "PLANIFIABLE"
        if mask_planif.any():
            df_be_raw = df_be_raw[mask_planif]

    # Construction d'un DF minimal pour la sélection
    df_be = pd.DataFrame()
    df_be["BE_Numero"] = (
        df_be_raw["BE_NUMERO"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    )
    df_be["Destination"] = (
        df_be_raw.get("BE_FK_DESTINATION", "")
        .astype(str)
        .str.strip()
    )
    df_be["Nb_Colis"] = (
        pd.to_numeric(df_be_raw.get("BE_NB_COLIS_P", 0), errors="coerce")
        .fillna(0)
        .astype(int)
    )
    df_be["Expediteur"] = (
        df_be_raw.get("BE_EXPEDITEUR", "").astype(str).str.strip()
    )
    df_be["Type"] = df_be_raw.get("BE_TYPE", "").astype(str).str.strip()

    df_be = df_be.drop_duplicates("BE_Numero")

    # Exclure les BE déjà dans le planning
    be_in_plan = set(df_plan["be"].astype(str).str.strip().unique())
    df_be_left = df_be[~df_be["BE_Numero"].isin(be_in_plan)]

    if df_be_left.empty:
        st.info("Tous les BE planifiables sont déjà dans ce planning.")
        return

    df_be_left = df_be_left.sort_values("BE_Numero")

    choice_be = st.selectbox(
        "Sélectionnez un BE :",
        df_be_left["BE_Numero"].tolist(),
        format_func=lambda x: f"BE {x}",
        key="upd_add_be",
    )

    sel = df_be_left[df_be_left["BE_Numero"] == choice_be].iloc[0]

    st.write(f"**Nombre de colis :** {sel['Nb_Colis']}")
    st.write(f"**Type :** {sel['Type']}")
    st.write(f"**Expéditeur :** {sel['Expediteur']}")
    st.write(f"**Destination (TDB) :** {sel['Destination']}")

    dest = str(sel["Destination"]).upper()

    # --- Vols disponibles ---
    dfs = st.session_state.get("dfs", {})
    df_vols = dfs.get("vols")

    if df_vols is None or df_vols.empty:
        st.error("⚠️ Vols non chargés (onglet Planning → Chargement).")
        return

    # Choix de la colonne de destination (IATA de préférence si dest=3 lettres)
    if len(dest) == 3 and "Dest_IATA" in df_vols.columns:
        dest_col = "Dest_IATA"
    else:
        possible_cols = ["Destination", "Destination_Nom", "Dest_IATA"]
        dest_col = next((c for c in possible_cols if c in df_vols.columns), None)

    if not dest_col:
        st.error("La colonne destination est introuvable dans df_vols.")
        return

    df_vols["dest_norm"] = df_vols[dest_col].astype(str).str.upper()

    vols_dest = df_vols[df_vols["dest_norm"] == dest].copy()
    vols_dest["Date_Vol"] = pd.to_datetime(vols_dest["Date_Vol"], errors="coerce")
    vols_dest = vols_dest.sort_values(["Date_Vol", "Heure_Vol"])

    if vols_dest.empty:
        st.warning(f"Aucun vol trouvé pour {dest} dans le fichier Vols.")
        return

    def label_vol(r):
        d = r["Date_Vol"].strftime("%d/%m") if not pd.isna(r["Date_Vol"]) else "??/??"
        h = r.get("Heure_Vol", "")
        return f"{d} — {h} — {r.get('Routing','')}"

    choice_vol = st.selectbox(
        "Choisir un vol :",
        vols_dest.index.tolist(),
        format_func=lambda idx: label_vol(vols_dest.loc[idx]),
        key="upd_add_vol",
    )

    rowv = vols_dest.loc[choice_vol]

    # --- Bénévoles disponibles ---
    df_benev = dfs.get("benev_param")
    df_dispo = dfs.get("benev_dispo")

    if df_benev is None or df_benev.empty:
        st.error("⚠️ Aucun bénévole chargé.")
        return

    df_benev["NomAff"] = df_benev["Prenom_Court"].astype(str) + " " + df_benev["Nom"]

    dispo = set()
    try:
        dte = rowv["Date_Vol"].date()
        dispo = set(
            df_dispo[
                pd.to_datetime(df_dispo["Date"], errors="coerce").dt.date == dte
            ]["Benevole"]
            .astype(str)
            .str.upper()
        )
    except Exception:
        pass

    bene_list = sorted(df_benev["NomAff"].tolist())

    def bene_label(n):
        return ("🟢 " if n.upper() in dispo else "⚪ ") + n

    choice_ben = st.selectbox(
        "Choisir un bénévole :",
        bene_list,
        format_func=bene_label,
        key="upd_add_benev",
    )

    if st.button("➕ Ajouter cette mise à bord", width="stretch"):

        new_row = {
            "date": rowv["Date_Vol"].strftime("%Y-%m-%d")
            if not pd.isna(rowv["Date_Vol"])
            else "",
            "nom": choice_ben,
            "destination_nom": rowv.get("Destination_Nom", dest),
            "destination_iata": dest,
            "routing": rowv.get("Routing", ""),
            "vol_info": rowv.get("Numero_Vol", ""),
            "heure": rowv.get("Heure_Vol", ""),
            "be": sel["BE_Numero"],
            "nb_colis": sel["Nb_Colis"],
            "type": sel["Type"],
            "expediteur": sel["Expediteur"],
            "destinataire": "",
        }

        st.session_state.setdefault("update_pending", []).append(("add", new_row))
        st.success("✔ BE ajouté.")


# ============================================================================
# 🔧 MODIFIER
# ============================================================================

def render_block_modify(df_plan):

    st.markdown("## 🔧 Modifier une mise à bord")

    if df_plan.empty:
        st.info("Aucun BE dans le planning.")
        return

    dfs = st.session_state.get("dfs", {})

    df_local = df_plan.copy()
    # Normalisation robuste des BE
    df_local["be"] = (
        df_local["be"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )

    be_list = sorted(
        df_local["be"].unique(),
        key=lambda x: int(str(x).strip().replace(".0", "")),
    )

    choice_be = st.selectbox(
        "Choisir un BE :",
        be_list,
        format_func=lambda x: f"BE {x}",
        key="upd_mod_be",
    )

    row = df_local[df_local["be"] == choice_be].iloc[0]
    dest = str(row["destination_iata"]).upper()

    st.write(f"**BE :** {choice_be}")
    st.write(f"**Destination :** {dest}")
    st.write(f"**Nb colis :** {row['nb_colis']}")
    st.write(f"**Type :** {row.get('type', '')}")
    st.write(f"**Expéditeur :** {row.get('expediteur', '')}")
    st.write(f"**Destinataire :** {row.get('destinataire', '')}")

    df_vols = dfs.get("vols")
    if df_vols is None or df_vols.empty:
        st.error("⚠️ Vols non chargés.")
        return

    # Sélection de la bonne colonne de destination
    if len(dest) == 3 and "Dest_IATA" in df_vols.columns:
        dest_col = "Dest_IATA"
    else:
        possible_cols = ["Destination", "Destination_Nom", "Dest_IATA"]
        dest_col = next((c for c in possible_cols if c in df_vols.columns), None)

    if not dest_col:
        st.error("La colonne destination est introuvable dans df_vols.")
        return

    df_vols["dest_norm"] = df_vols[dest_col].astype(str).str.upper()

    vols_dest = df_vols[df_vols["dest_norm"] == dest].copy()
    vols_dest["Date_Vol"] = pd.to_datetime(vols_dest["Date_Vol"], errors="coerce")
    vols_dest = vols_dest.sort_values(["Date_Vol", "Heure_Vol"])

    if vols_dest.empty:
        st.warning(f"Aucun vol trouvé pour {dest} dans le fichier Vols.")
        return

    def vol_label(v):
        d = v["Date_Vol"].strftime("%d/%m") if not pd.isna(v["Date_Vol"]) else "??/??"
        return f"{d} — {v.get('Heure_Vol','')} — {v.get('Routing','')}"

    keys = vols_dest.index.tolist()
    current_match = None
    for idx in keys:
        v = vols_dest.loc[idx]
        if (
            not pd.isna(v["Date_Vol"])
            and v["Date_Vol"].strftime("%Y-%m-%d") == str(row["date"])
            and str(v.get("Heure_Vol", "")).strip() == str(row.get("heure", "")).strip()
        ):
            current_match = idx
            break

    # --- Sélecteur de vol ---
    if current_match in keys:
        default_index = keys.index(current_match)
    else:
        default_index = 0

    choice_vol = st.selectbox(
        "Choisir un nouveau vol :",
        keys,
        index=default_index if keys else 0,
        format_func=lambda idx: vol_label(vols_dest.loc[idx])
        if idx in vols_dest.index
        else "Vol inconnu",
        key="upd_mod_vol",
    )

    if choice_vol not in vols_dest.index:
        st.error("⚠ Erreur interne : vol sélectionné introuvable.")
        return

    new_vol = vols_dest.loc[choice_vol]

    # --- Bénévoles ---
    df_benev = dfs.get("benev_param")
    df_dispo = dfs.get("benev_dispo")
    df_benev["NomAff"] = df_benev["Prenom_Court"].astype(str) + " " + df_benev["Nom"]

    dispo = set()
    try:
        dte = new_vol["Date_Vol"].date()
        dispo = set(
            df_dispo[
                pd.to_datetime(df_dispo["Date"], errors="coerce").dt.date == dte
            ]["Benevole"]
            .astype(str)
            .str.upper()
        )
    except Exception:
        pass

    bene_list = sorted(df_benev["NomAff"].tolist())

    def bene_label(n):
        return ("🟢 " if n.upper() in dispo else "⚪ ") + n

    choice_ben = st.selectbox(
        "Choisir un bénévole :",
        bene_list,
        index=bene_list.index(row["nom"]) if row["nom"] in bene_list else 0,
        format_func=bene_label,
        key="upd_mod_benev",
    )

    if st.button("💾 Enregistrer les modifications", width="stretch"):

        new_row = {
            "date": new_vol["Date_Vol"].strftime("%Y-%m-%d")
            if not pd.isna(new_vol["Date_Vol"])
            else row["date"],
            "nom": choice_ben,
            "destination_nom": new_vol.get("Destination_Nom", row["destination_nom"]),
            "destination_iata": dest,
            "routing": new_vol.get("Routing", row["routing"]),
            "vol_info": new_vol.get("Numero_Vol", row["vol_info"]),
            "heure": new_vol.get("Heure_Vol", row.get("heure", "")),
            "be": choice_be,
            "nb_colis": row.get("nb_colis", 0),
            "type": row.get("type", ""),
            "expediteur": row.get("expediteur", ""),
            "destinataire": row.get("destinataire", ""),
        }

        st.session_state.setdefault("update_pending", []).append(
            ("modify", choice_be, new_row)
        )
        st.success("✔ Modification enregistrée.")


# ============================================================================
# 🗑️ SUPPRIMER
# ============================================================================

def render_block_delete(df_plan):

    st.markdown("## 🗑️ Supprimer une mise à bord")

    if df_plan.empty:
        st.info("Planning vide.")
        return

    df_local = df_plan.copy()
    df_local["be"] = df_local["be"].astype(str)

    # Normalisation BE : enlever les .0 éventuels, convertir en entier
    def normalize_be(x):
        try:
            return int(float(str(x).strip()))
        except Exception:
            return None

    df_local["be_norm"] = df_local["be"].apply(normalize_be)

    valid_be = [b for b in df_local["be_norm"].unique() if b is not None]
    be_list = sorted(valid_be)

    if not be_list:
        st.info("Aucun BE valide à supprimer.")
        return

    choice_be = st.selectbox(
        "Choisir un BE à supprimer :",
        be_list,
        format_func=lambda x: f"BE {x}",
        key="upd_del_be",
    )

    # Sélection de la ligne à partir de be_norm
    row_sel = df_local[df_local["be_norm"] == choice_be]
    if row_sel.empty:
        st.error("⚠ Ligne introuvable pour ce BE (incohérence interne).")
        return

    row = row_sel.iloc[0]

    st.write(
        f"**Destination :** {row.get('destination_iata')} — {row.get('destination_nom')}"
    )
    st.write(
        f"**Vol :** {row.get('vol_info')} — {row.get('heure', '')} — {row.get('routing', '')}"
    )
    st.write(f"**Nb colis :** {row.get('nb_colis')}")
    st.write(f"**Type :** {row.get('type')}")
    st.write(f"**Expéditeur :** {row.get('expediteur')}")
    st.write(f"**Bénévole :** {row.get('nom')}")

    if st.button("❌ Confirmer suppression", width="stretch"):
        st.session_state.setdefault("update_pending", []).append(("delete", choice_be))
        st.success(f"✔ BE {choice_be} ajouté à la liste des suppressions.")


# ============================================================================
# 💾 APPLIQUER LES CHANGEMENTS
# ============================================================================

def render_block_apply_changes(df_plan):

    st.divider()
    st.markdown("## 💾 Appliquer les changements")

    pending = st.session_state.get("update_pending", [])

    if not pending:
        st.info("Aucune modification en attente.")
        return

    st.warning(f"{len(pending)} modification(s) en attente.")

    if st.button("💾 Appliquer toutes les modifications", width="stretch"):

        updated = df_plan.copy()

        for action in pending:
            atype = action[0]

            if atype == "delete":
                be_norm = str(action[1]).strip()
                # supprimer toutes les lignes dont le BE (normalisé) correspond
                def norm(x):
                    return str(x).strip().replace(".0", "")

                updated = updated[norm(updated["be"]) != be_norm]

            elif atype == "add":
                be_entry = action[1]
                updated = pd.concat(
                    [updated, pd.DataFrame([be_entry])], ignore_index=True
                )

            elif atype == "modify":
                be = str(action[1]).strip()
                fields = action[2]

                def norm(x):
                    return str(x).strip().replace(".0", "")

                mask = updated["be"].astype(str).apply(norm) == be

                for col, val in fields.items():
                    if col in updated.columns:
                        updated.loc[mask, col] = val
                    else:
                        # colonnes absentes → on les crée au besoin
                        updated[col] = updated.get(col, "")
                        updated.loc[mask, col] = val

        st.session_state["update_plan"] = updated
        st.session_state["update_pending"] = []

        st.success("✔ Planning mis à jour.")
        st.experimental_rerun()
