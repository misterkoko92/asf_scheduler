# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from asf_app.ui.ui_communication.helpers_email_tables import build_comm_table_html


def test_build_comm_table_html_escapes_values():
    df = pd.DataFrame(
        {
            "Date_Affichage": ["01/01"],
            "Destination": ["<b>TEST</b>"],
            "Numero_Vol_Aff": ["AF123"],
            "Numero_BE_Aff": ['"BE"'],
            "Nb_Colis": [1],
            "Type_Colis": ["<img src=x onerror=alert(1)>"] ,
            "Expediteur": ["ACME"],
            "Destinataire": ["Bob & Alice"],
        }
    )
    html = build_comm_table_html(df)
    assert "<b>" not in html
    assert "&lt;b&gt;TEST&lt;/b&gt;" in html
    assert "&lt;img" in html
    assert "&amp;" in html
    assert "&quot;BE&quot;" in html
