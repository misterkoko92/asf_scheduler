# asf_app/ui/ui_stats/stats_pdf.py
# -*- coding: utf-8 -*-

from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from pathlib import Path


def export_stats_pdf(images: list[str], path: Path):
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph("Statistiques ASFmm", styles["Title"]), Spacer(1, 20)]

    for img in images:
        story.append(Image(img, width=420, height=300))
        story.append(Spacer(1, 12))

    doc.build(story)
    return path
