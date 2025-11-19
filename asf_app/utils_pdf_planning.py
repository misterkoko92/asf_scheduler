# asf_app/utils_pdf_planning.py
# -*- coding: utf-8 -*-

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Spacer
from reportlab.lib.units import cm
from pathlib import Path
import pandas as pd


def generate_planning_pdf(df, pdf_path, logo_path=None):
    """
    Génère un PDF propre avec logo centré + tableau du planning.
    PDF sur 1 page en largeur (auto-ajusté).
    """

    # ---------------------------------------------------------
    # 1) Réordonnancement des colonnes et nettoyage
    # ---------------------------------------------------------
    df_pdf = df.copy()

    colonnes = [
        "Date_Vol", "Jour", "Heure_Vol", "Vol",
        "Destination_Nom", "BE_Numero", "BE_Nb_Colis",
        "BE_Type", "BE_Expediteur", "BE_Destinataire",
        "Benevole"
    ]

    df_pdf = df_pdf[colonnes].fillna("")

    # Convertit en liste de listes pour ReportLab
    data = [df_pdf.columns.tolist()] + df_pdf.values.tolist()

    # ---------------------------------------------------------
    # 2) Création PDF paysage A4
    # ---------------------------------------------------------
    pdf = SimpleDocTemplate(
        str(pdf_path),
        pagesize=landscape(A4),
        leftMargin=1 * cm,
        rightMargin=1 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1 * cm,
    )

    story = []

    # ---------------------------------------------------------
    # 3) Logo centré
    # ---------------------------------------------------------
    if logo_path and Path(logo_path).exists():
        try:
            img = Image(logo_path)
            img.drawHeight = 2.5 * cm
            img.drawWidth = img.drawHeight * 6  # ratio horizontal
            story.append(img)
            story.append(Spacer(1, 0.4 * cm))
        except Exception as e:
            print("Erreur chargement logo :", e)

    # ---------------------------------------------------------
    # 4) Préparation du tableau principal
    # ---------------------------------------------------------
    table = Table(data, repeatRows=1)

    # ---- Largeurs auto-ajustées ----
    col_widths = []
    for col in range(len(data[0])):
        max_len = max(len(str(row[col])) for row in data)
        width = max_len * 6
        width = max(50, min(width, 170))  # borne min/max
        col_widths.append(width)

    table._argW = col_widths

    # ---- Style tableau ----
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ("BOX", (0, 0), (-1, -1), 0.50, colors.black),
    ])

    table.setStyle(style)

    story.append(table)

    # ---------------------------------------------------------
    # 5) Génération finale PDF
    # ---------------------------------------------------------
    pdf.build(story)

    return True
