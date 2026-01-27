# asf_app/ui/ui_faq.py
# ---------------------
# Récapitulatif des règles et fonctionnement (FAQ / Instructions)

import streamlit as st


def render_tab_faq():
    st.title("❓ FAQ / Instructions")

    st.markdown("### Général")
    st.markdown(
        """
- Les sources OneDrive sont copiées en local dans un TMP **par session** (ex: `.tmp_asf/session_<id>/`).  
- Chargement **fail-fast** : si une source est introuvable, l’UI affiche l’erreur et stoppe la session.  
- Jamais de modification directe des sources OneDrive, sauf mises à jour MAG CENTRAL (col J/L) lors de l'export du planning.  
- Planning filtré : seuls les BE statut **D** depuis MAG CENTRAL sont planifiables.  
- Vols : uniquement départ **CDG**, capacité défaut 20 (fallback), routing normalisé avec `-`.  
- Dates : format FR souple, affichage `JJ/MM/AA` ou `Jour JJ/MM` selon contexte.
        """
    )

    st.markdown("### Onglet Fichiers d’entrée")
    st.markdown(
        """
- Affiche/charge les chemins OneDrive détectés (TDB, Bénévoles, Vols).  
- Copies locales auto dans un TMP de session.  
- Emplacements par défaut (OneDrive) :  
  - TABLEAU DE BORD : `.../Hélida/TABLEAU DE BORD.xlsx`  
    - Feuilles utilisées : **MAG CENTRAL** (BE statut D), **ParamBE**, **ParamExpediteur**, **ParamDest**, **ParamBenev**, **ParamBenevTéléphone** (selon column_map)  
  - PLANNING BÉNÉVOLES : `.../Planning Bénévoles/Planning BENEVOLE.xlsx` (fallback 2025 si besoin)  
    - Feuilles utilisées : **Disponibilités** (créneaux bénévoles)  
  - VOLS : `.../Planning MAB/Fichiers Source/aVols/Vols.xlsx`  
    - Feuilles utilisées : **Vols** (planning des vols)
        """
    )

    st.markdown("### Onglet Données Semaine")
    st.markdown(
        """
- Aperçus BE / Bénévoles / Vols de la semaine.  
- Hauteur de blocs réduite, colonnes d’index masquées.
        """
    )

    st.markdown("### Onglet Paramètres")
    st.markdown(
        """
- Réglages moteur/affichage.  
- Thème : switch Classique / Moderne (haut de page).
        """
    )

    st.markdown("### Onglet Planning V2 (OR-Tools)")
    st.markdown(
        """
- **Simulation OR-Tools** (2 modes) → planning + bilan en mémoire.  
- **Ajuster le planning simulé** : sélection BE (statut D) et vols filtrés par destination ; ajout / suppression.  
- **Export Excel** du planning simulé :  
  - Enrichissement complet.  
  - Mise à jour MAG CENTRAL source :  
    - Col J “DATE DE DEPART MAG” : si vide → vendredi de la semaine précédente ; sinon inchangé.  
    - Col L “DATE DEPART VOL” : date du vol planifié.  
  - Export maquette XLSX (feuille Planning SXX-YYYY, Export planning, Data Vols).  
  - Col O du planning = Date départ Mag (JJ/MM/AA).  
  - Message “MAG CENTRAL mis à jour…”.  
  - Export PDF uniquement via Excel (pas de fallback LibreOffice/brut) : si Excel non pilotable, pas de PDF.  
        """
    )

    st.markdown("### Onglet Communication")
    st.markdown(
        """
- df_comm construit depuis le planning enrichi.  
- Si aucun planning principal n’est disponible, utiliser le planning simulé (OR-Tools).  
- Whatsapp : messages générés, envoi via lien.  
- Emails Air France / ASF Interne :  
  - Joint uniquement le PDF si trouvé dans `Planning MAB/ASFmm PLANNING YYYY/ASFmm - PLANNING SEMAINE YYYY-XX-ZZ.pdf`.  
  - Sinon, warning “Pas de planning PDF trouvé - ajouter le manuellement.”  
  - Brouillons Outlook s’ouvrent au premier plan (mac/Windows).  
- Emails Destinataires / Expéditeurs : utilisent le planning enrichi, brouillons Outlook.
        """
    )

    st.markdown("### Onglet Statistiques")
    st.markdown(
        """
- Analyse des plannings Excel dans le dossier `ASFmm PLANNING YYYY` (tolérance sur noms).  
- Vue par défaut : année courante (fallback N-1), période annuelle.
        """
    )

    st.markdown("### Onglet Logs")
    st.markdown(
        """
- Affiche les logs chargés (état brut).  
        """
    )

    st.markdown("### Règles du moteur (création du planning)")
    st.markdown(
        """
- **Eligibilité BE** : seuls les BE statut **D** (MAG CENTRAL) sont planifiables.  
- **Priorité / Equiv** : priorité par type (ParamBE), calcul équiv colis via coeff ParamBE. Types inconnus → fallback priorité/coefficient par défaut.  
- **Vols** : uniquement départ **CDG** ; numéros normalisés “AF xxx” ; capacité par défaut 20 si non spécifiée. Routing normalisé avec “-”.  
- **Filtrage vols** : on retient les vols disponibles sur la période planifiée (lundi→dimanche), hors doublons.  
- **Tri BE** : par priorité puis équiv colis, avec gestion NON-ASF si applicable.  
- **Packing** : OR-Tools place les BE par destination selon les règles ParamDest ; rejet si pas de vol ou capacité insuffisante.  
- **Affectation bénévoles** : OR-Tools sélectionne les créneaux dispos (heures arr/dep), filtre par vol (charge), attribution en simple/double selon charge.  
- **Capacité bénévole** : ajuste la capacité équivalente d’un vol en fonction du nombre de bénévoles affectés (ex : 1 bénévole → cap réduite).  
- **Sortie** : planning enrichi (BE, vols, bénévoles, équiv, statuts), bilan BE/vols/bénévoles.  
- **Mise à jour MAG CENTRAL** (à l’export) : col J “DATE DE DEPART MAG” si vide → vendredi semaine précédente ; col L “DATE DEPART VOL” = date vol planifié.  
- **Export** : maquette Excel (feuilles Planning SXX-YYYY / Export planning / Data Vols) + PDF via Excel si autorisé.  
        """
    )

    st.markdown("### Export / fichiers")
    st.markdown(
        """
- Maquette utilisée : OneDrive `Planning MAB/ASFmm PLANNING 2025/aaSOURCE/Planning-maquette.xlsx` (fallback locale).  
- Feuilles : Planning SXX-YYYY, Export planning (brut), Data Vols (tableau avec filtres).  
- Version : nomme le fichier `ASFmm - PLANNING SEMAINE YYYY-XX-ZZ.xlsx` (ZZ = version, écrit en Q1).  
  Si l’incrément est désactivé, la version courante est déplacée dans le dossier `Historique`.
        """
    )

    st.markdown("### Limitations connues")
    st.markdown(
        """
- PDF : nécessite Excel pilotable (AppleScript/COM). Sinon aucun PDF généré (pas de fallback).  
- Écritures Excel : Excel automation si dispo (préserve validations + mises en forme conditionnelles). Fallback openpyxl peut supprimer validations / mises en forme conditionnelles.
        """
    )
