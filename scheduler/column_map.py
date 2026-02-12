# scheduler/column_map.py
# -*- coding: utf-8 -*-

"""
Mappings universels → colonnes normalisées.
Tout passe par loaders.universal_loader.load_and_normalize().
"""

# =============================================================================
#  MAG CENTRAL
# =============================================================================
column_map_mag_central = {
    "N° BE":                 "BE_Numero",
    "NB":                    "BE_Nb_Colis",
    "DEST":                  "Destination",
    "TYPE":                  "BE_Type",
    "Douane ?":              "BE_Douane",
    "EXP":                   "BE_Expediteur",
    "DESTINATAIRE":          "BE_Destinataire",
    "DATE IMPRESSION BE":    "BE_Date_Impression",
    "DATE CONDITIONNEMENT":  "BE_Date_Conditionnement",
    "DATE DE DEPART MAG":    "BE_Date_Depart_Mag",
    "DELAI DANS LE MAGASIN": "BE_Delai_Mag",
    "DATE DE DEPART VOL":    "BE_Date_Vol",
    "DELAI AU DEPART/PN1":   "BE_Delai_Depart",
    "Statut BE":               "BE_Statut",
    "Plannification Spéciale": "BE_Special",
    "Commentaires / Historique": "Commentaires",
    "Controle Planning OK / Litige / Résolu": "Controle_Planning",
    "Controle Expédition OK / Litige / Résolu2": "Controle_Expedition",
    "Controle Réception OK / Litige / Résolu": "Controle_Reception",
    "N° Facture":            "Numero_Facture",
    "Facture Envoyée":       "Facture_Envoyee",
    "Facture payée (vérif avec Compta)": "Facture_Payee",
    # Colonnes vides/techniques à ignorer
    "Unnamed: 22": "_IGNORE_22",
    "Unnamed: 23": "_IGNORE_23",
}

# =============================================================================
# ParamBE
# =============================================================================
column_map_param_be = {
    "Type":          "Type",
    "Priorite_Type": "Priorite_Type",
    "Equiv":         "Equiv",
}

# =============================================================================
# ParamDest
# =============================================================================
column_map_param_dest = {
    "Destination":       "Dest_IATA",
    "Ville":             "Dest_Ville",
    "PAYS":              "Dest_Pays",
    "Max_Colis_Par_Vol": "Max_Colis_Par_Vol",
    "Freq_Semaine":      "Freq_Semaine",
    "Lundi":             "Freq_Lundi",
    "Mardi":             "Freq_Mardi",
    "Mercredi":          "Freq_Mercredi",
    "Jeudi":             "Freq_Jeudi",
    "Vendredi":          "Freq_Vendredi",
    "Samedi":            "Freq_Samedi",
    "Dimanche":          "Freq_Dimanche",
    "Titre":             "Contact_Titre",
    "Nom":               "Contact_Nom",
    "Prénom":            "Contact_Prenom",
    "Mail":              "Contact_Email",
    "Copie":             "Contact_Copie",
    "Telephone 1":       "Contact_Tel1",
    "Telephone 2":       "Contact_Tel2",
    "Telephone 3":       "Contact_Tel3",
}

# =============================================================================
# ParamExpediteur
# =============================================================================
column_map_param_expediteur = {
    "Association":      "Expediteur_Nom",
    "Mail ASSO":        "Expediteur_Email",
    "Mail ASSO COPIE":  "Expediteur_Copie",
}

# =============================================================================
# Vols
# =============================================================================
column_map_vols = {
    "PVOL_FK_DESTINATION": "Destination_Nom",
    "PVOL_JOUR":           "Jour",
    "PVOL_DATE":           "Date_Vol",
    "PVOL_HEURE":          "Heure_Vol",
    "PVOL_NUMERO":         "Numero_Vol",
    "PVOL_FK_ESCALE":      "Escale",
    "PVOL_FK_ID":          "Flight_ID",
    "PVOL_ROUTE_API":      "Route_API",
    "base num vol":        "NumVol_Base",
    "base heure vol":      "Heure_Base",
    "base routing":        "Routing",
    # Colonnes techniques à ignorer
    "Unnamed: 11":         "_IGNORE_11",
}

# =============================================================================
# ParamBenev
# =============================================================================
column_map_param_benev = {
    "ID":                "ID",
    "BENEVOLE":          "Benevole",
    "NOM":               "Nom",
    "PRENOM":            "Prenom",
    "PRENOM_COURT":      "Prenom_Court",
    "Mail":              "Email",
    "MAX_COLIS_VOL":     "Max_Colis_Vol",
    "MAX COLIS VOL":     "Max_Colis_Vol",
    "MAX_JOURS_SEMAINE": "Max_Jours_Semaine",
    "MAX_EXP_SEMAINE":   "Max_Exp_Semaine",
    "MAX_EXP_JOUR":      "Max_Exp_Jour",
    "ATTENTE_MAX_H":     "Attente_Max_Heures",
    "Telephone":         "Telephone",
}

# =============================================================================
# Disponibilités
# =============================================================================
column_map_benev_dispo = {
    "ID":            "ID",
    "BENEVOLE":      "Benevole",
    "NOM":           "Nom",
    "PRENOM":        "Prenom",
    "PRENOM_COURT":  "Prenom_Court",
    "DATE":          "Date",
    "HEURE_ARRIVEE": "Heure_Arrivee",
    "HEURE_DEPART":  "Heure_Depart",
}
