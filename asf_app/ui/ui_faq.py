# asf_app/ui/ui_faq.py
# ---------------------
# Récapitulatif des règles et fonctionnement (FAQ / Instructions)

import streamlit as st


def render_tab_faq():
    st.title("❓ FAQ / Instructions")

    st.markdown("### Général")
    st.markdown(
        """
- Les sources OneDrive sont copiées en local dans `.tmp_asf` (TABLEAU DE BORD, PLANNING BENEVOLES, VOLS).  
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
- Copies locales auto dans `.tmp_asf`.  
- Emplacements par défaut (OneDrive) :  
  - TABLEAU DE BORD : `.../Hélida/TABLEAU DE BORD.xlsx`  
    - Feuilles utilisées : **MAG CENTRAL** (BE statut D), **ParamBE**, **ParamExpediteur**, **ParamDest**, **ParamBenev**, **ParamBenevTéléphone** (selon column_map)  
  - PLANNING BÉNÉVOLES : `.../Planning Bénévoles/Planning BENEVOLE 2025.xlsx`  
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

    st.markdown("### Onglet Planning")
    st.markdown(
        """
- **Générer** : exécute le moteur (mode real) → planning + bilan en mémoire (pas d’écriture fichiers).  
- **Modifier le planning** : sélection BE (statut D) et vols filtrés par destination ; boutons Mettre à jour / Supprimer.  
- **Bilan** : tableaux Expéditions / Vols / Bénévoles (statut planifié aligné sur l’aperçu).  
- **Valider & Exporter le planning Excel** :  
  - Enrichissement complet.  
  - Mise à jour MAG CENTRAL source :  
    - Col J “DATE DE DEPART MAG” : si vide → vendredi de la semaine précédente ; sinon inchangé.  
    - Col L “DATE DEPART VOL” : date du vol planifié.  
  - Export maquette XLSX (feuille Planning SXX-YYYY, Export planning, Data Vols).  
  - Col O du planning = Date départ Mag (JJ/MM/AA).  
  - Message “MAG CENTRAL mis à jour…”.  
  - Export PDF uniquement via Excel (pas de fallback LibreOffice/brut) : si Excel non pilotable, pas de PDF.  
- Preview planning brut : colonnes index masquées, numéros de vol format “AF xxx”.
        """
    )

    st.markdown("### Onglet Communication")
    st.markdown(
        """
- df_comm construit depuis le planning enrichi.  
- Whatsapp : messages générés, envoi via lien.  
- Emails Air France / ASF Interne :  
  - Joint uniquement le PDF si trouvé dans `Planning MAB/ASFmm PLANNING YYYY/ASFmm - PLANNING SEMAINE N° XX - YYYY.pdf`.  
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
- **Packing** : on place les BE par destination selon les règles ParamDest ; rejet si pas de vol ou capacité insuffisante.  
- **Affectation bénévoles** : sélection créneaux dispos (heures arr/dep), filtre par vol (charge), attribution en simple/double selon charge.  
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
- Suffixe version : si nom déjà existant, ajoute `-vXX` (cellule Q1) puis incrémente si collision.
        """
    )

    st.markdown("### Limitations connues")
    st.markdown(
        """
- PDF : nécessite Excel pilotable (AppleScript/COM). Sinon aucun PDF généré (pas de fallback).  
- MAG CENTRAL : écrit en direct (col J/L) mais openpyxl supprime les validations de données ; préservation des validations à prévoir en V2 via Excel automation.
        """
    )
