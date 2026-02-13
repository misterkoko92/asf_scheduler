# -*- coding: utf-8 -*-
from __future__ import annotations

import pandas as pd

from asf_app.ui.ui_simulation import (
    _apply_manual_assignment,
    _build_be_options,
    _build_bene_selector_data,
    _build_manual_row_data,
    _build_vol_selector_data,
    _clean_for_excel,
    _compute_bene_status,
    _compute_week_bounds,
    _compute_week_year,
    _delete_manual_assignment,
    _filter_vols_for_selection,
    _normalize_sort_plan,
    _recompute_be_non_planifies,
    _recompute_bilan,
    _recompute_bilan_benevoles,
    _recompute_dest_stats,
    _recompute_vols,
    _time_from_str,
)


def test_compute_week_year_prefers_current_state_values():
    df = pd.DataFrame([{"Date_Vol": "01/01/2026"}])
    week, year = _compute_week_year(df, current_week=12, current_year=2027)
    assert (week, year) == (12, 2027)


def test_compute_week_year_falls_back_to_planning_dates():
    df = pd.DataFrame([{"Date_Vol": "14/01/2026"}])
    week, year = _compute_week_year(df, current_week=None, current_year=None)
    assert (week, year) == (3, 2026)


def test_clean_for_excel_replaces_nan_with_none():
    df = pd.DataFrame([{"A": 1, "B": pd.NA}, {"A": 2, "B": None}])
    cleaned = _clean_for_excel(df)
    assert cleaned is not None
    assert cleaned.loc[0, "B"] is None
    assert cleaned.loc[1, "B"] is None


def test_recompute_bilan_marks_manual_rows():
    df_plan = pd.DataFrame(
        [
            {
                "Date_Vol": "01/01/2026",
                "Numero_Vol": "AF123",
                "Destination": "DLA",
                "BE_Numero": "260001",
                "BE_Nb_Colis": 2,
                "BE_Nb_Equiv": 2,
                "BE_Destinataire": "Hopital",
                "_MANUEL": True,
            }
        ]
    )
    out = _recompute_bilan(df_plan)
    assert len(out) == 1
    assert out.loc[0, "Raison"] == "MANUEL"
    assert bool(out.loc[0, "_MANUEL"]) is True


def test_recompute_bilan_includes_non_partants_with_reason():
    df_plan = pd.DataFrame(
        [
            {
                "Date_Vol": "01/01/2026",
                "Numero_Vol": "AF123",
                "Destination": "DLA",
                "BE_Numero": "260001",
                "BE_Nb_Colis": 2,
                "BE_Nb_Equiv": 2,
                "BE_Destinataire": "Hopital",
            }
        ]
    )
    df_be_src = pd.DataFrame(
        [
            {"BE_Numero": "260001", "Destination": "DLA", "BE_Nb_Colis": 2, "Equiv_Colis": 2},
            {"BE_Numero": "260002", "Destination": "RUN", "BE_Nb_Colis": 1, "Equiv_Colis": 1},
            {"BE_Numero": "260003", "Destination": "TNR", "BE_Nb_Colis": 3, "Equiv_Colis": 4, "Raison": "Pas de vol compatible"},
        ]
    )

    out = _recompute_bilan(df_plan, df_be_src=df_be_src)

    assert len(out) == 3
    partants = out[out["Partant"] == "OUI"]
    non_partants = out[out["Partant"] == "NON"]
    assert len(partants) == 1
    assert len(non_partants) == 2
    assert set(non_partants["BE_Numero"].astype(str)) == {"260002", "260003"}
    r_map = {str(r["BE_Numero"]): str(r["Raison"]) for _, r in non_partants.iterrows()}
    assert r_map["260002"] == "NON AFFECTE"
    assert r_map["260003"] == "Pas de vol compatible"


def test_recompute_bilan_enriches_non_partant_reasons_with_context():
    df_plan = pd.DataFrame(
        [
            {
                "Date_Vol": "20/01/26",
                "Heure_Vol": "10:00",
                "Numero_Vol": "AF100",
                "Destination": "DLA",
                "BE_Numero": "260001",
                "BE_Nb_Equiv": 20,
            }
        ]
    )
    df_be_src = pd.DataFrame(
        [
            {"BE_Numero": "260001", "Destination": "DLA", "BE_Nb_Colis": 2, "Equiv_Colis": 20},
            {"BE_Numero": "260002", "Destination": "DLA", "BE_Nb_Colis": 1, "Equiv_Colis": 1},
            {"BE_Numero": "260003", "Destination": "RUN", "BE_Nb_Colis": 1, "Equiv_Colis": 1},
            {"BE_Numero": "260004", "Destination": "TNR", "BE_Nb_Colis": 1, "Equiv_Colis": 1},
        ]
    )
    df_vols_src = pd.DataFrame(
        [
            {"Date_Vol": "20/01/26", "Heure_Vol": "10h00", "Numero_Vol": "AF100", "IATA": "DLA", "Max_Colis": 20},
            {"Date_Vol": "21/01/26", "Heure_Vol": "11h00", "Numero_Vol": "AF200", "IATA": "TNR", "Max_Colis": 20},
        ]
    )
    df_dispo_src = pd.DataFrame(
        [
            {
                "Benevole": "ALICE",
                "Date_dt": pd.Timestamp("2026-01-20"),
                "Heure_Arrivee_time": pd.Timestamp("09:00").time(),
                "Heure_Depart_time": pd.Timestamp("12:00").time(),
            }
        ]
    )

    out = _recompute_bilan(
        df_plan,
        df_be_src=df_be_src,
        df_vols_src=df_vols_src,
        df_dispo_src=df_dispo_src,
        start_dt=pd.Timestamp("2026-01-19"),
        end_dt=pd.Timestamp("2026-01-25"),
    )

    non_partants = out[out["Partant"] == "NON"]
    assert len(non_partants) == 3
    r_map = {str(r["BE_Numero"]): str(r["Raison"]) for _, r in non_partants.iterrows()}
    assert r_map["260002"] == "Capacité vols atteinte sur la période"
    assert r_map["260003"] == "Aucun vol vers RUN sur la période"
    assert r_map["260004"] == "Aucun bénévole disponible sur les créneaux vols"


def test_recompute_vols_aggregates_be_and_benevole_counts():
    df_plan = pd.DataFrame(
        [
            {"Date_Vol": "01/01/2026", "Numero_Vol": "AF123", "Destination": "DLA", "Heure_Vol": "10:00", "BE_Numero": "1", "Benevole": "A"},
            {"Date_Vol": "01/01/2026", "Numero_Vol": "AF123", "Destination": "DLA", "Heure_Vol": "10:00", "BE_Numero": "2", "Benevole": "B"},
            {"Date_Vol": "01/01/2026", "Numero_Vol": "AF123", "Destination": "DLA", "Heure_Vol": "10:00", "BE_Numero": "3", "Benevole": "B"},
        ]
    )
    out = _recompute_vols(df_plan)
    assert len(out) == 1
    assert int(out.loc[0, "Nb_BE"]) == 3
    assert int(out.loc[0, "Nb_Benevoles"]) == 2


def test_recompute_dest_stats_adds_existing_and_used_flights():
    df_plan = pd.DataFrame(
        [
            {"Date_Vol": "19/01/26", "Heure_Vol": "11h00", "Numero_Vol": "AF822", "Destination": "CONAKRY", "BE_Numero": "1", "BE_Nb_Colis": 2, "BE_Nb_Equiv": 2},
            {"Date_Vol": "19/01/26", "Heure_Vol": "11:00", "Numero_Vol": "AF822", "Destination": "CONAKRY", "BE_Numero": "2", "BE_Nb_Colis": 3, "BE_Nb_Equiv": 3},
            {"Date_Vol": "20/01/26", "Heure_Vol": "11:00", "Numero_Vol": "AF948", "Destination": "CONAKRY", "BE_Numero": "3", "BE_Nb_Colis": 1, "BE_Nb_Equiv": 1},
        ]
    )
    df_vols = pd.DataFrame(
        [
            {"Date_Vol": "19/01/26", "Heure_Vol": "11h00", "Numero_Vol": "AF822", "IATA": "CKY"},
            {"Date_Vol": "20/01/26", "Heure_Vol": "11h00", "Numero_Vol": "AF823", "IATA": "CKY"},
            {"Date_Vol": "21/01/26", "Heure_Vol": "11h00", "Numero_Vol": "AF824", "IATA": "CKY"},
            {"Date_Vol": "22/01/26", "Heure_Vol": "11h00", "Numero_Vol": "AF825", "IATA": "CKY"},
            {"Date_Vol": "23/01/26", "Heure_Vol": "11h00", "Numero_Vol": "AF826", "IATA": "CKY"},
            {"Date_Vol": "24/01/26", "Heure_Vol": "11h00", "Numero_Vol": "AF827", "IATA": "CKY"},
            {"Date_Vol": "25/01/26", "Heure_Vol": "11h00", "Numero_Vol": "AF828", "IATA": "CKY"},
        ]
    )
    df_paramdest = pd.DataFrame(
        [
            {
                "Dest_IATA": "CKY",
                "Dest_Ville": "CONAKRY",
                "Freq_Lundi": 1,
                "Freq_Mardi": 1,
                "Freq_Mercredi": 1,
                "Freq_Jeudi": 1,
                "Freq_Vendredi": 1,
                "Freq_Samedi": 0,
                "Freq_Dimanche": 0,
            }
        ]
    )

    out = _recompute_dest_stats(
        df_plan,
        df_vols_src=df_vols,
        df_paramdest=df_paramdest,
        start_dt=pd.Timestamp("2026-01-19"),
        end_dt=pd.Timestamp("2026-01-25"),
    )

    row = out[out["Destination"] == "CONAKRY"].iloc[0]
    assert int(row["Nb_Vols_Existant"]) == 5
    assert int(row["Nb_Vols_Utilises"]) == 2


def test_recompute_be_non_planifies_filters_planned_numbers():
    df_plan = pd.DataFrame([{"BE_Numero": "260001"}])
    df_be = pd.DataFrame([{"BE_Numero": "260001"}, {"BE_Numero": "260002"}])
    out = _recompute_be_non_planifies(df_plan, df_be)
    assert list(out["BE_Numero"].astype(str)) == ["260002"]


def test_recompute_bilan_benevoles_computes_requested_metrics():
    df_plan = pd.DataFrame(
        [
            {"Benevole": "ALICE", "Date_Vol": "20/01/26", "Heure_Vol": "10h00", "Numero_Vol": "AF100", "BE_Numero": "BE1"},
            {"Benevole": "ALICE", "Date_Vol": "20/01/26", "Heure_Vol": "10:00", "Numero_Vol": "AF100", "BE_Numero": "BE2"},
            {"Benevole": "ALICE", "Date_Vol": "20/01/26", "Heure_Vol": "14:30", "Numero_Vol": "AF200", "BE_Numero": "BE3"},
            {"Benevole": "ALICE", "Date_Vol": "21/01/26", "Heure_Vol": "09:00", "Numero_Vol": "AF300", "BE_Numero": "BE4"},
            {"Benevole": "BOB", "Date_Vol": "21/01/26", "Heure_Vol": "09:00", "Numero_Vol": "AF300", "BE_Numero": "BE4"},
        ]
    )
    df_dispo = pd.DataFrame(
        [
            {
                "Benevole": "ALICE",
                "Date_dt": pd.Timestamp("2026-01-20"),
                "Heure_Arrivee_time": pd.Timestamp("10:00").time(),
                "Heure_Depart_time": pd.Timestamp("12:00").time(),
            },
            {
                "Benevole": "ALICE",
                "Date_dt": pd.Timestamp("2026-01-21"),
                "Heure_Arrivee_time": pd.Timestamp("10:00").time(),
                "Heure_Depart_time": pd.Timestamp("12:00").time(),
            },
            {
                "Benevole": "ALICE",
                "Date_dt": pd.Timestamp("2026-01-22"),
                "Heure_Arrivee_time": pd.Timestamp("10:00").time(),
                "Heure_Depart_time": pd.Timestamp("12:00").time(),
            },
            # invalide -> ne compte pas dans Nb_Dispo
            {
                "Benevole": "ALICE",
                "Date_dt": pd.Timestamp("2026-01-23"),
                "Heure_Arrivee_time": None,
                "Heure_Depart_time": pd.Timestamp("12:00").time(),
            },
        ]
    )
    df_parambenev = pd.DataFrame([{"Benevole": "ALICE"}, {"Benevole": "BOB"}, {"Benevole": "CHARLIE"}])

    out = _recompute_bilan_benevoles(
        df_plan,
        df_dispo,
        df_parambenev=df_parambenev,
        start_dt=pd.Timestamp("2026-01-19"),
        end_dt=pd.Timestamp("2026-01-25"),
    )

    assert "Nb_Dispo" in out.columns
    assert "Nb_Jours_Affectes" in out.columns
    assert "Nb_Vols_Affectes" in out.columns
    assert "Nb_BE_Affectes" in out.columns

    alice = out[out["Benevole"] == "ALICE"].iloc[0]
    assert int(alice["Nb_Dispo"]) == 3
    assert int(alice["Nb_Jours_Affectes"]) == 2
    assert int(alice["Nb_Vols_Affectes"]) == 3
    assert int(alice["Nb_BE_Affectes"]) == 4

    bob = out[out["Benevole"] == "BOB"].iloc[0]
    assert int(bob["Nb_Dispo"]) == 0
    assert int(bob["Nb_Jours_Affectes"]) == 1
    assert int(bob["Nb_Vols_Affectes"]) == 1
    assert int(bob["Nb_BE_Affectes"]) == 1

    charlie = out[out["Benevole"] == "CHARLIE"].iloc[0]
    assert int(charlie["Nb_Dispo"]) == 0
    assert int(charlie["Nb_Jours_Affectes"]) == 0
    assert int(charlie["Nb_Vols_Affectes"]) == 0
    assert int(charlie["Nb_BE_Affectes"]) == 0


def test_compute_week_bounds_from_api_dates_and_planning_fallback():
    start, end = _compute_week_bounds(
        api_start_date="2026-01-19",
        api_end_date="2026-01-25",
        planning_df=pd.DataFrame(),
    )
    assert str(start.date()) == "2026-01-19"
    assert str(end.date()) == "2026-01-25"

    start2, end2 = _compute_week_bounds(
        api_start_date=None,
        api_end_date=None,
        planning_df=pd.DataFrame([{"Date_Vol": "20/01/2026"}, {"Date_Vol": "22/01/2026"}]),
    )
    assert str(start2.date()) == "2026-01-20"
    assert str(end2.date()) == "2026-01-22"


def test_time_from_str_parses_and_handles_invalid():
    out = _time_from_str("10h30")
    assert out is not None
    assert out.hour == 10
    assert out.minute == 30
    assert _time_from_str("") is None
    assert _time_from_str("not-a-time") is None


def test_build_be_options_sorts_and_formats_labels():
    df_be = pd.DataFrame(
        [
            {"Destination": "RUN", "BE_Numero": "260002", "BE_Nb_Colis": 2, "BE_Type": "MM"},
            {"Destination": "DLA", "BE_Numero": "260001", "BE_Nb_Colis": 1, "BE_Type": "FRET"},
        ]
    )
    out = _build_be_options(df_be, planned_set={"260001"})
    assert len(out) == 2
    assert out[0][0] == "DLA"
    assert out[0][1] == "260001"
    assert "(déjà au planning)" in out[0][2]
    assert "(non planifié)" in out[1][2]


def test_filter_vols_for_selection_filters_destination_and_period():
    df_vols = pd.DataFrame(
        [
            {"Date_Vol": "2026-01-20", "IATA": "RUN", "Destination": "RUN", "Routing": "CDG-RUN"},
            {"Date_Vol": "2026-01-20", "IATA": "DLA", "Destination": "DLA", "Routing": "CDG-DLA"},
            {"Date_Vol": "2026-01-30", "IATA": "RUN", "Destination": "RUN", "Routing": "CDG-RUN"},
        ]
    )
    out = _filter_vols_for_selection(
        df_vols,
        code_iata_be="RUN",
        api_start_date="2026-01-19",
        api_end_date="2026-01-25",
    )
    assert len(out) == 1
    assert out.iloc[0]["IATA"] == "RUN"


def test_build_vol_selector_data_for_unplanned_and_planned():
    df_vols_filt = pd.DataFrame(
        [
            {
                "Date_Vol": "2026-01-23",
                "Numero_Vol": "AF652",
                "Heure_Vol": "10:30",
                "Routing": "CDG-RUN",
                "IATA": "RUN",
                "Destination": "RUN",
            }
        ]
    )
    plan_df = pd.DataFrame(
        [
            {"Date_Vol": "2026-01-23", "Numero_Vol": "AF652"},
        ]
    )
    labels, values, idx = _build_vol_selector_data(
        df_vols_filt,
        plan_df,
        code_iata_be="RUN",
        planned_row=None,
    )
    assert labels[0].startswith("BE absent du planning")
    assert values[0] == ("", "", "")
    assert idx == 0

    planned_row = pd.Series({"Date_Vol": "2026-01-23", "Numero_Vol": "AF652"})
    labels2, values2, idx2 = _build_vol_selector_data(
        df_vols_filt,
        plan_df,
        code_iata_be="RUN",
        planned_row=planned_row,
    )
    assert idx2 == 0
    assert values2[0][1] == "AF652"
    assert "déjà utilisé" in labels2[0]


def test_build_vol_selector_data_deduplicates_multistop_physical_flight():
    df_vols_filt = pd.DataFrame(
        [
            {
                "Date_Vol": "2026-02-16",
                "Numero_Vol": "AF822",
                "Heure_Vol": "11h00",
                "Routing": "CDG-SSG-DLA",
                "IATA": "SSG",
                "Destination": "SSG",
            },
            {
                "Date_Vol": "2026-02-16",
                "Numero_Vol": "AF822",
                "Heure_Vol": "11h00",
                "Routing": "CDG-SSG-DLA",
                "IATA": "DLA",
                "Destination": "DLA",
            },
        ]
    )
    plan_df = pd.DataFrame()
    planned_row = pd.Series({"Date_Vol": "2026-02-16", "Numero_Vol": "AF822"})

    labels, values, idx = _build_vol_selector_data(
        df_vols_filt,
        plan_df,
        code_iata_be="DLA",
        planned_row=planned_row,
    )

    assert idx == 0
    assert len(values) == 1
    assert values[0] == ("2026-02-16", "AF822", "11h00")
    assert labels[0].count("AF 822") == 1
    assert labels[0].count("CDG-SSG-DLA") == 1


def test_compute_bene_status_and_selector_data():
    benev_existing = pd.DataFrame(
        [
            {"Benevole": "ALICE", "Numero_Vol": "AF652", "Date_Vol": "2026-01-23"},
        ]
    )
    df_dispo = pd.DataFrame(
        [
            {
                "Benevole": "BOB",
                "Date_dt": "2026-01-23",
                "Heure_Arrivee_time": pd.Timestamp("10:00").time(),
                "Heure_Depart_time": pd.Timestamp("12:00").time(),
            }
        ]
    )

    status_alice = _compute_bene_status(
        name="ALICE",
        benev_existing=benev_existing,
        df_dispo=df_dispo,
        vol_choice_val="AF652",
        date_choice="2026-01-23",
        heure_choice="11:00",
    )
    assert status_alice == "Occupé"

    status_bob = _compute_bene_status(
        name="BOB",
        benev_existing=benev_existing,
        df_dispo=df_dispo,
        vol_choice_val="AF999",
        date_choice="2026-01-23",
        heure_choice="11:00",
    )
    assert status_bob == "Disponible"

    df_parambenev = pd.DataFrame([{"Benevole": "ALICE"}, {"Benevole": "BOB"}])
    labels, values, sel = _build_bene_selector_data(
        df_parambenev=df_parambenev,
        df_dispo=df_dispo,
        benev_existing=benev_existing,
        vol_choice_val="AF652",
        date_choice="2026-01-23",
        heure_choice="11:00",
        planned_row=None,
    )
    assert labels[0].startswith("BE absent du planning")
    assert values[0] == ""
    assert sel == 0

    labels2, values2, sel2 = _build_bene_selector_data(
        df_parambenev=df_parambenev,
        df_dispo=df_dispo,
        benev_existing=benev_existing,
        vol_choice_val="AF652",
        date_choice="2026-01-23",
        heure_choice="11:00",
        planned_row=pd.Series({"Benevole": "ALICE"}),
    )
    assert values2[sel2] == "ALICE"


def test_build_manual_row_data_uses_benevole_metadata():
    be_row = pd.Series(
        {
            "BE_Nb_Colis": 2,
            "Equiv_Colis": 3,
            "BE_Expediteur": "EXP",
            "BE_Destinataire": "DEST",
            "BE_Type": "MM",
        }
    )
    df_parambenev = pd.DataFrame(
        [
            {"Benevole": "ALICE", "ID": "42", "Telephone": "0600000000"},
        ]
    )
    out = _build_manual_row_data(
        be_num="260001",
        code_iata_be="RUN",
        date_choice="2026-01-23",
        heure_choice="10:30",
        vol_choice_val="AF652",
        be_row=be_row,
        benev_val="ALICE",
        df_parambenev=df_parambenev,
    )
    assert out["BE_Numero"] == "260001"
    assert out["Destination"] == "RUN"
    assert out["BE_Nb_Colis"] == 2
    assert out["BE_Nb_Equiv"] == 3
    assert out["ID"] == "42"
    assert out["Telephone"] == "0600000000"
    assert out["_MANUEL"] is True


def test_apply_and_delete_manual_assignment_and_normalize_sort():
    df_plan = pd.DataFrame(
        [
            {
                "BE_Numero": "260001",
                "Destination": "RUN",
                "Date_Vol": "2026-01-23",
                "Heure_Vol": "10:30",
                "Numero_Vol": "AF652",
            }
        ]
    )
    row_data = {
        "BE_Numero": "260001",
        "Destination": "DLA",
        "Date_Vol": "2026-01-24",
        "Heure_Vol": "12:00",
        "Numero_Vol": "AF968",
        "_MANUEL": True,
    }
    out_update = _apply_manual_assignment(df_plan, be_num="260001", row_data=row_data)
    assert len(out_update) == 1
    assert out_update.iloc[0]["Destination"] == "DLA"
    assert bool(out_update.iloc[0]["_MANUEL"]) is True

    out_add = _apply_manual_assignment(df_plan, be_num="260002", row_data={**row_data, "BE_Numero": "260002"})
    assert len(out_add) == 2
    assert set(out_add["BE_Numero"].astype(str)) == {"260001", "260002"}

    out_delete = _delete_manual_assignment(out_add, be_num="260001")
    assert list(out_delete["BE_Numero"].astype(str)) == ["260002"]

    out_sorted = _normalize_sort_plan(
        pd.DataFrame(
            [
                {"BE_Numero": "260002", "Date_Vol": "2026-01-25", "Heure_Vol": "11:00", "Numero_Vol": "AF001"},
                {"BE_Numero": "260001", "Date_Vol": "2026-01-23", "Heure_Vol": "10:00", "Numero_Vol": "AF001"},
            ]
        )
    )
    assert list(out_sorted["BE_Numero"].astype(str)) == ["260001", "260002"]
