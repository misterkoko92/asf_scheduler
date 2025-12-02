# whatsapp_handler.py — Version Communication 3.0
# ---------------------------------------------------------
# Génère 1 message WhatsApp par bénévole, à partir du tableau df_comm
# produit par clean_planning_df.py.
# ---------------------------------------------------------

import urllib.parse
import platform
import subprocess
import pandas as pd
import re

def _encode_for_whatsapp(text: str) -> str:
    """Encode proprement un texte en UTF-8 + URL encoding."""
    if not text:
        return ""
    return urllib.parse.quote(text, safe="")


def _open_whatsapp(url: str):
    """Ouvre WhatsApp sans envoyer le message (Mac/Windows)."""
    system = platform.system().lower()
    if "darwin" in system:          # macOS
        subprocess.Popen(["open", url])
    elif "windows" in system:
        subprocess.Popen(["cmd", "/c", "start", "", url], shell=True)
    else:
        # fallback Linux
        subprocess.Popen(["xdg-open", url])

# Outil : normalisation destination (priorité ville, fallback code)
def _normalize_dest(df, default_col="Destination"):
    return (
        df.get("Dest_Ville", "")
        .fillna(df.get(default_col, ""))
        .fillna(df.get("DESTINATION", ""))
        .astype(str)
        .str.strip()
        .str.upper()
    )


# =====================================================================
# MESSAGE PAR BENEVOLE
# =====================================================================
def _build_message_for_benevole(df_bene, vols_info, map_iata_city):
    """Construit le message final pour un bénévole."""

    # Prénom d’affichage (priorité prénom complet, sinon premier mot du nom complet, sinon prénom court)
    prenom_full = df_bene.get("Benevole_Prenom", pd.Series([""])).fillna("")
    prenom_court = df_bene.get("Benevole_Prenom_Court", pd.Series([""])).fillna("")
    bene_nom_complet = df_bene.get("BENEVOLE", df_bene.get("Benevole", pd.Series([""]))).fillna("")
    prenom = prenom_full.iloc[0] if not prenom_full.empty else ""
    if not prenom and not bene_nom_complet.empty:
        prenom = str(bene_nom_complet.iloc[0]).strip().split()[0]
    if not prenom and not prenom_court.empty:
        prenom = prenom_court.iloc[0]
    prenom_aff = str(prenom).strip().split()[0] if prenom else ""
    if not prenom_aff:
        prenom_aff = " "

    # Message d’entête
    lignes = []
    lignes.append(f"Bonjour {prenom_aff}, voici tes mises à bord pour la semaine prochaine :")

    # Harmoniser quelques colonnes pour éviter les trous
    df_bene = df_bene.copy()
    df_bene["Destination"] = df_bene.get("Destination", df_bene.get("DESTINATION", ""))
    df_bene["Dest_Ville"] = df_bene.get("Dest_Ville", df_bene.get("Destination", ""))
    df_bene["Code_IATA"] = df_bene.get("Code_IATA", df_bene.get("Dest_IATA", df_bene.get("DESTINATION", "")))
    df_bene["Heure_Vol_Aff"] = df_bene.get("Heure_Vol_Aff", df_bene.get("HEURE VOL", ""))
    df_bene["Numero_Vol_Aff"] = df_bene.get("Numero_Vol_Aff", df_bene.get("NUMERO VOL", ""))
    df_bene["Type_Colis"] = df_bene.get("Type_Colis", df_bene.get("TYPE", ""))
    df_bene["Numero_BE_Aff"] = df_bene.get("Numero_BE_Aff", df_bene.get("NUMERO BE", ""))

    # Fallback vol/destination si encore vide
    df_bene["Numero_Vol_Aff"] = (
        df_bene["Numero_Vol_Aff"]
        .replace(["", None, pd.NA], pd.NA)
        .fillna(df_bene.get("Vol", ""))
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .apply(lambda x: f"AF {x}" if x and not str(x).upper().startswith("AF") else str(x))
    )
    df_bene["Destination"] = (
        df_bene["Destination"]
        .replace(["", None, pd.NA], pd.NA)
        .fillna(df_bene.get("Dest_Ville", df_bene.get("DESTINATION", "")))
    )
    df_bene["Destination_norm"] = _normalize_dest(df_bene)

    # On regroupe par vol pour insérer le total juste après
    df_bene_sorted = df_bene.sort_values(
        by=["DATE", "Destination_norm", "Numero_Vol_Aff", "Heure_Vol_Aff"]
    )

    for (date, dest_norm, vol_num), df_vol in df_bene_sorted.groupby(["DATE", "Destination_norm", "Numero_Vol_Aff"]):
        # lignes détail pour ce vol
        for _, row in df_vol.iterrows():
            iata_raw = str(row.get("Code_IATA", "")).strip().upper()
            dest_city = (
                str(row.get("Dest_Ville", "")).strip().upper()
                or str(row.get("Destination", "")).strip().upper()
                or str(row.get("DESTINATION", "")).strip().upper()
            )
            if not dest_city and iata_raw:
                dest_city = map_iata_city.get(iata_raw, iata_raw)
            iata_display = iata_raw or dest_city
            dest_display = dest_city or iata_display
            date_display = row.get("Date_Affichage_WA", row.get("DATE", ""))
            date_key = str(row.get("DATE", ""))
            code_key = iata_display
            vol_key = row.get("Numero_Vol_Aff", "")

            heure_display = str(row.get("Heure_Vol_Aff", row.get("HEURE VOL", "")))
            if ":" in heure_display:
                parts = heure_display.split(":")
                if len(parts) >= 2:
                    heure_display = f"{parts[0].zfill(2)}h{parts[1][:2].zfill(2)}"

            nb_colis = row.get("Nb_Colis", 0)
            try:
                nb_colis = int(nb_colis)
            except Exception:
                nb_colis = 0
            ligne = (
                f"• {date_display} : "
                f"{dest_display} // "
                f"{row.get('Numero_Vol_Aff', '')} // "
                f"{heure_display} // "
                f"BE {row.get('Numero_BE_Aff', '')} // "
                f"{nb_colis} colis {row.get('Type_Colis', '')}"
            )
            lignes.append(ligne)

        # total pour ce vol
        key = (str(date), iata_display or dest_norm, vol_num)
        info = vols_info.get(key, {})
        total = info.get("total_colis", 0)
        bene_set = info.get("benevoles", {})
        nb_bene = len(bene_set)
        iata_total = info.get("iata", iata_display)

        mode = {1: "en simple", 2: "en double", 3: "en triple"}.get(
            nb_bene, f"avec {nb_bene} bénévoles"
        )

        bene_current = df_bene["_BENE_KEY"].iloc[0] if "_BENE_KEY" in df_bene.columns else df_bene.get("BENEVOLE_ID", df_bene.get("BENEVOLE", ""))

        autres = []
        for bid, (pcourt, nom) in bene_set.items():
            bid_cmp = bid or str(df_vol.get("BENEVOLE", "")).strip().upper()
            if bid_cmp != bene_current:
                pc = (pcourt or "").strip()
                nm = str(nom or "").strip().upper()
                label = f"{pc} {nm}".strip()
                autres.append(label)
        if nb_bene >= 2 and autres:
            mode += " avec " + ", ".join(autres)

        lignes.append(f"Total {iata_total or dest_norm or dest_display} : {total} colis {mode}")
        lignes.append("")  # saut de ligne entre vols

    # ------------------------------------------------------------------
    # Ajout des totals (déjà insérés dans la boucle)
    # ------------------------------------------------------------------

    # Signature finale
    lignes.append("Merci de me confirmer si tu es OK. N'hésite pas à m'appeler si besoin pour ajuster.")
    lignes.append("Merci beaucoup !")

    return "\n".join(lignes)


# =====================================================================
# CALCUL DES GROUPES VOL (TOUS BÉNÉVOLES)
# =====================================================================
def _compute_vols_info(df_comm):
    """
    Pré-calcul des totaux par vol (tous bénévoles confondus).
    Clé vol = (DATE, Dest_Ville, Numero_Vol_Aff)
    """
    info = {}

    df_comm = df_comm.copy()
    df_comm["Destination_norm"] = _normalize_dest(df_comm)
    # clé bénévole robuste (ID ou nom)
    def _bene_key(row):
        bid = str(row.get("BENEVOLE_ID", "")).strip()
        if not bid or bid.lower() == "nan":
            bid = str(row.get("BENEVOLE", row.get("Benevole", ""))).strip().upper()
        return bid
    df_comm["_BENE_KEY"] = df_comm.apply(_bene_key, axis=1)
    df_comm["Dest_Ville"] = df_comm.get("Dest_Ville", df_comm.get("Destination", df_comm.get("DESTINATION", "")))
    df_comm["Code_IATA"] = df_comm.get("Code_IATA", df_comm.get("Dest_IATA", df_comm.get("DESTINATION", "")))
    df_comm["Numero_Vol_Aff"] = (
        df_comm.get("Numero_Vol_Aff", df_comm.get("NUMERO VOL", df_comm.get("Vol", "")))
        .replace(["", None, pd.NA], pd.NA)
        .fillna(df_comm.get("Vol", ""))
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .apply(lambda x: f"AF {x}" if x and not str(x).upper().startswith("AF") else str(x))
    )

    df_comm["Dest_Key"] = df_comm["Code_IATA"].replace("", pd.NA).fillna(df_comm["Destination_norm"])

    grouped = df_comm.groupby(["DATE", "Dest_Key", "Numero_Vol_Aff"], dropna=False)
    for (date, dest_key, vol_num), df_tmp in grouped:

        total = pd.to_numeric(df_tmp["Nb_Colis"], errors="coerce").fillna(0).astype(int).sum()

        # Bénévoles distincts sur ce vol
        bene_dict = {}
        for _, row in df_tmp.iterrows():
            bid = row.get("_BENE_KEY", row.get("BENEVOLE_ID", ""))
            # prénom court prioritaire, sinon initiale du prénom complet, sinon initiale du nom complet
            pcourt = (
                row.get("Benevole_Prenom_Court")
                or row.get("Prenom_Court")
                or ""
            )
            if not pcourt:
                pref = str(row.get("Benevole_Prenom", "")).strip()
                if pref:
                    pcourt = f"{pref[0].upper()}."
            if not pcourt:
                full = str(row.get("BENEVOLE", row.get("Benevole", ""))).strip()
                if full:
                    pcourt = f"{full.split()[0][0].upper()}."
            nom_val = row.get("Benevole_Nom", "") or row.get("Nom", "")
            if not nom_val:
                full = str(row.get("BENEVOLE", row.get("Benevole", ""))).strip()
                parts = full.split()
                if len(parts) >= 2:
                    nom_val = " ".join(parts[1:])
            nom = str(nom_val or "").upper()
            bene_dict[bid] = (pcourt, nom)

        # Premier code IATA disponible pour ce vol
        iata_val = df_tmp["Code_IATA"].replace(["", None, pd.NA], pd.NA).dropna()
        iata_val = iata_val.iloc[0] if not iata_val.empty else ""

        info[(str(date), dest_key, vol_num)] = {
            "total_colis": total,
            "benevoles": bene_dict,
            "iata": iata_val,
        }

    return info


# =====================================================================
# FUNCTION PRINCIPALE
# =====================================================================
def generate_whatsapp_messages(df_comm):
    """
    Construit la liste :
    [
      {"benevole":..., "telephone":..., "message":..., "url":...},
      ...
    ]
    """

    if df_comm is None or df_comm.empty:
        return []

    # Colonnes clés garanties
    if "BENEVOLE" not in df_comm.columns:
        df_comm["BENEVOLE"] = df_comm.get("Benevole", "")
    if "BENEVOLE_ID" not in df_comm.columns:
        df_comm["BENEVOLE_ID"] = df_comm.get("ID_BENEVOLE", df_comm.get("ID", ""))

    # clé bénévole robuste : ID si dispo, sinon nom
    def _bene_key(row):
        bid = str(row.get("BENEVOLE_ID", "")).strip()
        if not bid or bid.lower() == "nan":
            bid = str(row.get("BENEVOLE", row.get("Benevole", ""))).strip().upper()
        return bid

    df_comm["_BENE_KEY"] = df_comm.apply(_bene_key, axis=1)

    # pré-calcul vols
    vols_info = _compute_vols_info(df_comm)
    # mapping IATA -> ville pour affichage
    map_iata_city = (
        df_comm[["Code_IATA", "Dest_Ville"]]
        .dropna()
        .drop_duplicates()
        .set_index("Code_IATA")["Dest_Ville"]
        .to_dict()
    )

    # liste unique de bénévoles (clé robuste)
    bene_ids = [k for k in df_comm["_BENE_KEY"].unique() if k]

    messages = []

    for bid in bene_ids:
        df_bene = df_comm[df_comm["_BENE_KEY"] == bid].copy()
        if df_bene.empty:
            continue

        bene_col = "BENEVOLE" if "BENEVOLE" in df_bene.columns else "Benevole"

        # téléphone (nettoyage chiffres)
        raw_tel = df_bene.get("Benevole_Tel", df_bene.get("Telephone", "")).iloc[0]
        tel = re.sub(r"\D", "", str(raw_tel))
        if not tel:
            continue  # pas de téléphone = on skip

        # génération du message
        message = _build_message_for_benevole(df_bene, vols_info, map_iata_city)

        # encodage
        encoded = _encode_for_whatsapp(message)
        url = f"https://wa.me/{tel}?text={encoded}"

        messages.append({
            "benevole": df_bene[bene_col].iloc[0],
            "telephone": tel,
            "message": message,
            "url": url
        })

    return messages


# =====================================================================
# OUVERTURE WHATSAPP POUR UN BÉNÉVOLE
# =====================================================================
def open_whatsapp_for_benevole(url):
    """Ouvre simplement l’URL WhatsApp correspondante."""
    _open_whatsapp(url)
