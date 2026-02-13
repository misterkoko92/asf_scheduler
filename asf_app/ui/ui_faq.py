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
    - Feuilles utilisées : **Disponibilités** (créneaux bénévoles), **ParamBenev** (dont `MAX_COLIS_VOL`)  
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
- **Paramoteur** : choix de la version solver **V2/V3** (par défaut V3).
        """
    )

    st.markdown("### Onglet Planning")
    st.markdown(
        """
- **Génération OR-Tools** (2 modes) → planning + bilan en mémoire.  
- Modes OR-Tools :  
  - **Priorité Colis** : maximise le colis puis minimise le nombre de bénévoles affectés.  
  - **Priorité Bénévole** : maximise le colis puis maximise le nombre de bénévoles mobilisés.  
  - Si les 2 modes donnent le même résultat, c’est souvent dû à des contraintes identiques (ex: aucun bénévole compatible sur les vols).  
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
- Choix de source : **Planning de la session** (moteur principal / OR-Tools) ou **Planning OneDrive**.  
- Planning OneDrive : sélectionner l’année, choisir un fichier Excel dans `ASFmm PLANNING YYYY`, puis cliquer **Valider**.  
  La feuille **“Export planning”** est utilisée pour générer les messages.  
- Si aucun planning de session n’est disponible, le mode OneDrive reste utilisable.  
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
- **Vols multi-escales** : chaque escale est considérée comme destination candidate (ex: `CDG-SSG-DLA` expose `SSG` et `DLA`).  
- **Unicité vol physique** : un même vol (même date/heure/numéro) ne peut pas transporter simultanément 2 destinations différentes.  
- **Règle de conflit multi-escales** : si conflit, la première destination du routing est prioritaire.  
- **Filtrage vols** : on retient les vols disponibles sur la période planifiée (lundi→dimanche), hors doublons.  
- **Tri BE** : par priorité puis équiv colis, avec gestion NON-ASF si applicable.  
- **Packing** : OR-Tools place les BE par destination selon les règles ParamDest ; rejet si pas de vol ou capacité insuffisante.  
- **Affectation bénévoles** : OR-Tools sélectionne les créneaux dispos (heures arr/dep), filtre par vol (charge), attribution en simple/double selon charge.  
- **Capacité bénévole (V3)** : contrainte **stricte par bénévole** via `MAX_COLIS_VOL` (ParamBenev), fallback 22 si vide/≤0.  
- **Capacité bénévole (V2)** : capacité globale par vol basée sur le nombre de bénévoles affectés.  
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

    st.markdown("### Bilans détaillés (simulation)")
    st.markdown(
        """
- Ordre d’affichage : **Bilan des bénévoles** → **Bilan des expéditions** → **Bilan des vols** → **Bilan par destination** → **Planning Bénévoles**.  
- Bilan bénévoles :  
  - `Nb_Dispo` = nombre de jours avec disponibilité valide sur la période.  
  - `Nb_Jours_Affectes` = nombre de jours distincts avec au moins un vol affecté.  
  - `Nb_Vols_Affectes` = nombre de vols distincts affectés.  
  - `Nb_BE_Affectes` = nombre de BE affectés.  
- Bilan expéditions : inclut les BE partants et non partants avec motif (`Aucun vol`, `Aucun bénévole`, `Capacité atteinte`, `Conflit de contraintes`, etc.).  
- Bilan destination : inclut `Nb_Vols_Existant` (après règles ParamDest) et `Nb_Vols_Utilises`.  
        """
    )

    st.markdown("### Limitations connues")
    st.markdown(
        """
- PDF : nécessite Excel pilotable (AppleScript/COM). Sinon aucun PDF généré (pas de fallback).  
- Écritures Excel : Excel automation si dispo (préserve validations + mises en forme conditionnelles). Fallback openpyxl peut supprimer validations / mises en forme conditionnelles.
        """
    )
