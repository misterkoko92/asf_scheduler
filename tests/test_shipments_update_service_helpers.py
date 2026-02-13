# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, time

import pandas as pd

import asf_app.services.shipments_update_service as sus


def _base_export_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "BE_Numero": "250001",
                "BE_Key": "250001",
                "Date_Vol": date(2025, 1, 1),
                "Heure_Vol": time(10, 0),
                "BE_Nb_Colis": "",
                "BE_Nb_Equiv": "",
                "BE_Type": "",
                "BE_Expediteur": "",
                "BE_Destinataire": "",
                "ID": "12",
                "Telephone": "0101",
                "_STATUS": "normal",
            }
        ]
    )


def test_apply_update_to_export_df_annulation_marks_old_only():
    df = _base_export_df()

    out = sus._apply_update_to_export_df(
        df,
        action="Annulation",
        be_num="250001",
        dest_iata="DLA",
        date_new="",
        vol_new="",
        heure_new="",
        bene_choice="",
        be_info={},
        plan_row_full={},
        bene_meta=None,
        bene_changed=False,
    )

    assert len(out) == 1
    assert out.loc[0, "_STATUS"] == "old"


def test_apply_update_to_export_df_replanification_adds_new_row_and_fallbacks():
    df = _base_export_df()

    out = sus._apply_update_to_export_df(
        df,
        action="Replanification",
        be_num="250001",
        dest_iata="DLA",
        date_new="02/01/2025",
        vol_new="AF123",
        heure_new="11:30",
        bene_choice="DUPONT",
        be_info={
            "BE_Nb_Colis": 3,
            "BE_Type": "MM",
            "BE_Expediteur": "ASF",
            "BE_Destinataire": "Hopital",
        },
        plan_row_full={},
        bene_meta={"ID": "77", "Telephone": "0909"},
        bene_changed=False,
    )

    assert len(out) == 2
    old_rows = out[out["_STATUS"] == "old"]
    new_rows = out[out["_STATUS"] == "new"]
    assert len(old_rows) == 1
    assert len(new_rows) == 1

    row = new_rows.iloc[0]
    assert row["BE_Numero"] == "250001"
    assert row["Destination"] == "DLA"
    assert row["IATA"] == "DLA"
    assert row["Date_Vol"] == date(2025, 1, 2)
    assert row["Heure_Vol"] == time(11, 30)
    assert row["Heure"] == "11h30"
    assert int(row["HEURE_MIN"]) == 11 * 60 + 30
    assert row["Numero_Vol"] == "AF123"
    assert row["Benevole"] == "DUPONT"
    assert int(row["BE_Nb_Colis"]) == 3
    assert int(row["BE_Nb_Equiv"]) == 3
    assert row["BE_Type"] == "MM"
    assert row["BE_Expediteur"] == "ASF"
    assert row["BE_Destinataire"] == "Hopital"
    assert row["ID"] == "12"
    assert row["Telephone"] == "0101"


def test_apply_update_to_export_df_uses_plan_row_fallback_and_bene_changed_meta():
    df = _base_export_df()
    df.loc[0, "ID"] = ""
    df.loc[0, "Telephone"] = ""

    out = sus._apply_update_to_export_df(
        df,
        action="Changement de date ou bénévole",
        be_num="250001",
        dest_iata="DLA",
        date_new="03/01/2025",
        vol_new="AF456",
        heure_new="12:00",
        bene_choice="MARTIN",
        be_info={},
        plan_row_full={
            "NB_COLIS": 2,
            "BE_Equiv_Colis": 4,
            "TYPE": "FRET",
            "EXPEDITEUR": "EXP",
            "DESTINATAIRE": "DEST",
        },
        bene_meta={"ID": "99", "Telephone": "0600"},
        bene_changed=True,
    )

    row = out[out["_STATUS"] == "new"].iloc[0]
    assert int(row["BE_Nb_Colis"]) == 2
    assert int(row["BE_Nb_Equiv"]) == 4
    assert row["BE_Type"] == "FRET"
    assert row["BE_Expediteur"] == "EXP"
    assert row["BE_Destinataire"] == "DEST"
    assert row["ID"] == "99"
    assert row["Telephone"] == "0600"


def test_sort_export_df_orders_by_date_time_and_be():
    df = pd.DataFrame(
        [
            {"BE_Numero": "250002", "Date_Vol": date(2025, 1, 2), "Heure_Vol": time(11, 0)},
            {"BE_Numero": "250001", "Date_Vol": date(2025, 1, 2), "Heure_Vol": time(10, 0)},
            {"BE_Numero": "250003", "Date_Vol": date(2025, 1, 1), "Heure_Vol": time(12, 0)},
        ]
    )

    out = sus._sort_export_df(df)
    assert out["BE_Numero"].tolist() == ["250003", "250001", "250002"]


def test_load_export_df_returns_empty_when_excel_is_invalid(monkeypatch, tmp_path):
    path = tmp_path / "broken.xlsx"
    path.write_text("not-an-excel", encoding="utf-8")

    def _raise_value_error(*_args, **_kwargs):
        raise ValueError("invalid")

    monkeypatch.setattr(sus.pd, "read_excel", _raise_value_error)

    out = sus._load_export_df(path)

    assert isinstance(out, pd.DataFrame)
    assert out.empty
    assert "BE_Key" in out.columns
    assert "_STATUS" in out.columns
