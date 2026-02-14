# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt

import pandas as pd

import asf_app.ui.ui_shipments_update_helpers as sh
from asf_app.ui.ui_shipments_update_helpers import (
    _add_queue_item,
    _apply_queue_action_to_session,
    _apply_queue_add_to_session,
    _bene_status,
    _build_action_selection_data,
    _build_action_sentence,
    _build_asf_notification_draft,
    _build_assignment_summary,
    _build_bene_meta,
    _build_bene_options,
    _build_body_lines_multi,
    _build_default_bene_label,
    _build_default_vol_tuple,
    _build_destination_notification_drafts,
    _build_duplicate_be_warning,
    _build_expediteur_notification_drafts,
    _build_lookup_be_selector_data,
    _build_notification_payloads,
    _build_planif_be_options,
    _build_planifiable_be_selector_data,
    _build_planning_version_choices,
    _build_queue_dataframe,
    _build_queue_item,
    _build_queue_labels,
    _build_sent_drafts_feedback,
    _build_vol_selection_data,
    _build_week_selector_data,
    _clear_queue_state,
    _coerce_display_types,
    _collect_apply_result_feedback,
    _collect_be_from_planning,
    _collect_benevole_emails,
    _dedupe_queue_by_be,
    _dest_to_iata,
    _execute_queue_add_request,
    _execute_queue_apply_request,
    _extract_bene_choice,
    _fill_bene_name_from_parambenev,
    _find_row_in_df,
    _format_be_option_label,
    _format_preview_dataframe,
    _group_payloads_by_destination,
    _group_payloads_by_expediteur,
    _load_be_sources_for_week,
    _load_export_planning_sheet,
    _merge_emails,
    _normalize_be_key_for_select,
    _notification_period_from_payloads,
    _open_file_in_os,
    _pop_prefill_values,
    _prepare_be_lookup,
    _prepare_dispo,
    _prepare_notification_context,
    _prepare_queue_apply,
    _queue_to_batch_updates,
    _queue_transition_after_action,
    _resolve_assignment_from_plan_row,
    _resolve_current_bene_identity,
    _resolve_lookup_be_row,
    _resolve_notification_pdf_path,
    _resolve_planning_version_major,
    _resolve_selected_vol,
    _run_queue_apply_batch,
    _select_source_for_be,
    _send_named_outlook_drafts,
    _send_named_outlook_drafts_with_feedback,
    _send_outlook_draft,
    _should_show_mag_central_cleanup_info,
    _weeks_from_status_df,
)


def test_build_action_sentence_variants():
    cancel = _build_action_sentence(
        be_num="250001",
        dest_iata="RUN",
        date_initial="23 janvier 2026",
        action="Annulation",
        new_date="",
        vol_disp="",
        bene_short="",
    )
    assert "sera annulé" in cancel

    add = _build_action_sentence(
        be_num="250001",
        dest_iata="RUN",
        date_initial="",
        action="Ajouter au planning",
        new_date="24 janvier 2026",
        vol_disp="AF 652",
        bene_short="P DUPONT",
    )
    assert "sera ajouté le 24 janvier 2026 sur le vol AF 652" in add

    repl = _build_action_sentence(
        be_num="250001",
        dest_iata="RUN",
        date_initial="23 janvier 2026",
        action="Changement de date ou bénévole",
        new_date="24 janvier 2026",
        vol_disp="AF 652",
        bene_short="P DUPONT",
    )
    assert "sera reprogrammé le 24 janvier 2026 sur le vol AF 652" in repl


def test_build_action_selection_data_by_source_and_prefill():
    options_plan, idx_plan = _build_action_selection_data(
        be_source="planning",
        prefill_action="Changement de date ou bénévole",
    )
    assert options_plan == ["Annulation", "Changement de date ou bénévole"]
    assert idx_plan == 1

    options_mag, idx_mag = _build_action_selection_data(
        be_source="mag_central",
        prefill_action="Annulation",
    )
    assert options_mag == ["Ajouter au planning"]
    assert idx_mag == 0


def test_merge_emails_splits_and_dedupes_case_insensitive():
    out = _merge_emails(
        "a@test.com; b@test.com",
        ["B@test.com, c@test.com", "a@test.com"],
        None,
    )
    assert out == ["a@test.com", "b@test.com", "c@test.com"]


def test_normalize_be_key_for_select_handles_year_and_prefixes():
    assert _normalize_be_key_for_select("20251234") == "251234"
    assert _normalize_be_key_for_select("001234", year=2026) == "261234"
    assert _normalize_be_key_for_select("1234", year=2026) == "261234"
    assert _normalize_be_key_for_select("1234") == "001234"


def test_dedupe_queue_by_be_keeps_last_modification():
    queue = [
        {"be_num": "250001", "action": "A"},
        {"be_num": "250002", "action": "B"},
        {"be_num": "BE 250001", "action": "C"},
    ]
    deduped, ignored = _dedupe_queue_by_be(queue)
    assert [d["action"] for d in deduped] == ["B", "C"]
    assert ignored == ["250001"]


def test_queue_to_batch_updates_maps_expected_fields():
    out = _queue_to_batch_updates(
        [
            {
                "action": "Annulation",
                "be_num": "250001",
                "dest_iata": "RUN",
                "date_new": "2026-01-23",
                "vol_new": "AF652",
                "heure_new": "11:00",
                "bene_choice": "DUPONT",
            }
        ]
    )
    assert len(out) == 1
    assert out[0]["action"] == "Annulation"
    assert out[0]["be_num"] == "250001"
    assert out[0]["be_info"] == {}
    assert out[0]["plan_row_full"] == {}
    assert out[0]["bene_meta"] == {}
    assert out[0]["bene_changed"] is False


def test_prepare_queue_apply_validates_path_and_dedupes(tmp_path):
    queue = [
        {"be_num": "250001", "action": "A"},
        {"be_num": "250002", "action": "B"},
        {"be_num": "BE 250001", "action": "C"},
    ]
    planning = tmp_path / "planning.xlsx"
    planning.touch()

    queue_path, deduped, ignored, err = _prepare_queue_apply(
        queue,
        queue_path=None,
        preview_path=planning,
    )
    assert err is None
    assert queue_path == planning
    assert [d["action"] for d in deduped] == ["B", "C"]
    assert ignored == ["250001"]

    queue_path2, deduped2, ignored2, err2 = _prepare_queue_apply(
        queue,
        queue_path=tmp_path / "missing.xlsx",
        preview_path=None,
    )
    assert queue_path2 is None
    assert deduped2 == []
    assert ignored2 == []
    assert "Impossible de trouver le fichier planning" in str(err2)


def test_queue_transition_after_action_edit_delete_clear_and_invalid():
    queue = [{"be_num": "250001"}, {"be_num": "250002"}]

    edited = _queue_transition_after_action(queue, index=1, action="edit")
    assert [q["be_num"] for q in edited["queue"]] == ["250001"]
    assert edited["prefill"]["be_num"] == "250002"
    assert edited["message"] is None
    assert edited["is_empty"] is False

    deleted = _queue_transition_after_action(queue, index=0, action="delete")
    assert [q["be_num"] for q in deleted["queue"]] == ["250002"]
    assert deleted["prefill"] is None
    assert deleted["message"] == "Modification supprimée."
    assert deleted["is_empty"] is False

    cleared = _queue_transition_after_action(queue, index=0, action="clear")
    assert cleared["queue"] == []
    assert cleared["prefill"] is None
    assert cleared["message"] == "Liste vidée."
    assert cleared["is_empty"] is True

    invalid = _queue_transition_after_action(queue, index=9, action="delete")
    assert invalid["queue"] == queue
    assert invalid["message"] is None


def test_apply_queue_action_to_session_edit_delete_and_clear():
    session_state = {
        "ship_update_queue": [{"be_num": "250001"}, {"be_num": "250002"}],
        "ship_update_queue_planning_path": "/tmp/planning.xlsx",
        "ship_update_queue_week": 4,
        "ship_update_queue_year": 2026,
        "ship_update_payloads": [{"id": 1}],
    }

    transition_edit = _apply_queue_action_to_session(
        session_state,
        queue=session_state["ship_update_queue"],
        index=1,
        action="edit",
    )
    assert [q["be_num"] for q in session_state["ship_update_queue"]] == ["250001"]
    assert session_state["ship_update_prefill"]["be_num"] == "250002"
    assert transition_edit["prefill"]["be_num"] == "250002"

    transition_delete = _apply_queue_action_to_session(
        session_state,
        queue=session_state["ship_update_queue"],
        index=0,
        action="delete",
    )
    assert session_state["ship_update_queue"] == []
    assert transition_delete["is_empty"] is True
    assert "ship_update_queue_planning_path" not in session_state
    assert "ship_update_payloads" in session_state

    session_state["ship_update_queue"] = [{"be_num": "250010"}]
    session_state["ship_update_queue_planning_path"] = "/tmp/planning.xlsx"
    session_state["ship_update_queue_week"] = 5
    session_state["ship_update_queue_year"] = 2026
    transition_clear = _apply_queue_action_to_session(
        session_state,
        queue=session_state["ship_update_queue"],
        index=0,
        action="clear",
        clear_payloads_on_clear=True,
    )
    assert transition_clear["message"] == "Liste vidée."
    assert session_state["ship_update_queue"] == []
    assert "ship_update_queue_planning_path" not in session_state
    assert "ship_update_payloads" not in session_state


def test_build_duplicate_be_warning_message():
    msg = _build_duplicate_be_warning(["250001", "250002", "250001"])
    assert "Plusieurs modifications sur le même BE détectées" in str(msg)
    assert "250001" in str(msg)
    assert "250002" in str(msg)
    assert _build_duplicate_be_warning([]) is None


def test_should_show_mag_central_cleanup_info():
    assert (
        _should_show_mag_central_cleanup_info(
            write_mag_central=True,
            deduped=[{"action": "Annulation"}],
        )
        is True
    )
    assert (
        _should_show_mag_central_cleanup_info(
            write_mag_central=False,
            deduped=[{"action": "Annulation"}],
        )
        is False
    )
    assert (
        _should_show_mag_central_cleanup_info(
            write_mag_central=True,
            deduped=[{"action": "Ajouter au planning"}],
        )
        is False
    )


def test_run_queue_apply_batch_success_and_payloads(tmp_path):
    planning = tmp_path / "planning.xlsx"
    planning.touch()
    updated = tmp_path / "updated.xlsx"
    updated.touch()
    generated_pdf = tmp_path / "updated.pdf"
    generated_pdf.touch()

    captured: dict[str, object] = {}

    def fake_apply(path, updates, **kwargs):
        captured["path"] = path
        captured["updates"] = updates
        captured["kwargs"] = kwargs
        return updated

    def fake_pdf(_path):
        return generated_pdf

    deduped = [
        {
            "action": "Annulation",
            "be_num": "250001",
            "dest_iata": "RUN",
            "date_new": "2026-01-23",
            "vol_new": "AF652",
            "heure_new": "11:00",
            "bene_choice": "ALICE",
        }
    ]
    out = _run_queue_apply_batch(
        queue_path=planning,
        deduped=deduped,
        queue_week=None,
        queue_year=None,
        selected_week=4,
        selected_year=2026,
        df_vols=pd.DataFrame(),
        df_parambenev=pd.DataFrame(),
        df_dispos=pd.DataFrame(),
        df_paramdest=pd.DataFrame(),
        increment_q1=True,
        write_mag_central=True,
        tdb_source_path="/tmp/tdb.xlsx",
        apply_updates_fn=fake_apply,
        export_pdf_fn=fake_pdf,
    )
    assert out["error"] is None
    assert out["updated_path"] == updated
    assert out["pdf_path"] == generated_pdf
    assert out["pdf_error"] is None
    assert out["week"] == 4
    assert out["year"] == 2026
    assert len(out["payloads"]) == 1
    assert out["payloads"][0]["planning_path"] == str(updated)
    assert out["payloads"][0]["planning_pdf_path"] == str(generated_pdf)
    assert captured["path"] == planning
    assert isinstance(captured["updates"], list)
    assert captured["kwargs"]["increment_version"] is True
    assert captured["kwargs"]["write_mag_central"] is True
    assert captured["kwargs"]["week"] == 4
    assert captured["kwargs"]["year"] == 2026


def test_run_queue_apply_batch_apply_error_and_pdf_error(tmp_path):
    planning = tmp_path / "planning.xlsx"
    planning.touch()
    deduped = [{"action": "Annulation", "be_num": "250001"}]

    def failing_apply(_path, _updates, **_kwargs):
        raise RuntimeError("boom")

    out_fail = _run_queue_apply_batch(
        queue_path=planning,
        deduped=deduped,
        queue_week=4,
        queue_year=2026,
        selected_week=1,
        selected_year=2000,
        df_vols=None,
        df_parambenev=None,
        df_dispos=None,
        df_paramdest=None,
        increment_q1=True,
        write_mag_central=True,
        tdb_source_path=None,
        apply_updates_fn=failing_apply,
        export_pdf_fn=lambda _p: _p,
    )
    assert "Erreur lors de la mise à jour du planning : boom" == out_fail["error"]
    assert out_fail["updated_path"] is None
    assert out_fail["pdf_path"] is None
    assert out_fail["payloads"] == []

    def ok_apply(path, _updates, **_kwargs):
        return path

    def failing_pdf(_path):
        raise RuntimeError("no pdf")

    out_pdf = _run_queue_apply_batch(
        queue_path=planning,
        deduped=deduped,
        queue_week=4,
        queue_year=2026,
        selected_week=1,
        selected_year=2000,
        df_vols=None,
        df_parambenev=None,
        df_dispos=None,
        df_paramdest=None,
        increment_q1=True,
        write_mag_central=True,
        tdb_source_path=None,
        apply_updates_fn=ok_apply,
        export_pdf_fn=failing_pdf,
    )
    assert out_pdf["error"] is None
    assert out_pdf["updated_path"] == planning
    assert out_pdf["pdf_path"] is None
    assert out_pdf["pdf_error"] == "no pdf"
    assert len(out_pdf["payloads"]) == 1
    assert out_pdf["payloads"][0]["planning_pdf_path"] == ""


def test_execute_queue_apply_request_handles_missing_path_and_run_outcomes(tmp_path):
    # Missing planning path -> prepare error
    out_missing = _execute_queue_apply_request(
        queue=[{"be_num": "250001"}],
        queue_path=None,
        preview_path=None,
        queue_week=4,
        queue_year=2026,
        selected_week=4,
        selected_year=2026,
        df_vols=None,
        df_parambenev=None,
        df_dispos=None,
        df_paramdest=None,
        increment_q1=True,
        write_mag_central=True,
        tdb_source_path=None,
        apply_updates_fn=lambda *_args, **_kwargs: None,
        export_pdf_fn=lambda p: p,
    )
    assert "Impossible de trouver le fichier planning" in str(out_missing["error"])
    assert out_missing["payloads"] == []

    planning = tmp_path / "planning.xlsx"
    planning.touch()
    queue = [
        {"be_num": "250001", "action": "A"},
        {"be_num": "BE 250001", "action": "B"},
    ]

    captured: dict[str, object] = {}

    def fake_run_success(**kwargs):
        captured.update(kwargs)
        return {
            "error": None,
            "updated_path": planning,
            "pdf_path": None,
            "pdf_error": "pdf-failed",
            "payloads": [{"be_num": "250001"}],
            "week": 4,
            "year": 2026,
        }

    out_success = _execute_queue_apply_request(
        queue=queue,
        queue_path=planning,
        preview_path=None,
        queue_week=4,
        queue_year=2026,
        selected_week=4,
        selected_year=2026,
        df_vols=pd.DataFrame(),
        df_parambenev=pd.DataFrame(),
        df_dispos=pd.DataFrame(),
        df_paramdest=pd.DataFrame(),
        increment_q1=True,
        write_mag_central=True,
        tdb_source_path=None,
        apply_updates_fn=lambda *_args, **_kwargs: planning,
        export_pdf_fn=lambda p: p,
        run_queue_apply_batch_fn=fake_run_success,
    )
    assert out_success["error"] is None
    assert "Plusieurs modifications sur le même BE" in str(out_success["warning"])
    assert len(out_success["deduped"]) == 1
    assert out_success["updated_path"] == planning
    assert out_success["pdf_error"] == "pdf-failed"
    assert out_success["payloads"] == [{"be_num": "250001"}]
    assert captured["queue_path"] == planning
    assert len(captured["deduped"]) == 1

    def fake_run_error(**_kwargs):
        return {
            "error": "boom",
            "updated_path": None,
            "pdf_path": None,
            "pdf_error": None,
            "payloads": [],
        }

    out_error = _execute_queue_apply_request(
        queue=queue,
        queue_path=planning,
        preview_path=None,
        queue_week=4,
        queue_year=2026,
        selected_week=4,
        selected_year=2026,
        df_vols=pd.DataFrame(),
        df_parambenev=pd.DataFrame(),
        df_dispos=pd.DataFrame(),
        df_paramdest=pd.DataFrame(),
        increment_q1=True,
        write_mag_central=True,
        tdb_source_path=None,
        apply_updates_fn=lambda *_args, **_kwargs: planning,
        export_pdf_fn=lambda p: p,
        run_queue_apply_batch_fn=fake_run_error,
    )
    assert out_error["error"] == "boom"
    assert out_error["updated_path"] is None
    assert out_error["payloads"] == []


def test_collect_apply_result_feedback_messages_and_open_paths(tmp_path):
    updated = tmp_path / "updated.xlsx"
    updated.touch()
    pdf = tmp_path / "updated.pdf"
    pdf.touch()

    feedback = _collect_apply_result_feedback(
        {
            "updated_path": updated,
            "pdf_path": pdf,
            "pdf_error": None,
            "deduped": [{"action": "Annulation"}],
        },
        write_mag_central=True,
    )
    assert any("Planning Excel mis à jour" in msg for msg in feedback["success_messages"])
    assert any("PDF généré" in msg for msg in feedback["success_messages"])
    assert any("MAG CENTRAL source nettoyé" in msg for msg in feedback["info_messages"])
    assert feedback["warning_messages"] == []
    assert feedback["open_paths"] == [updated, pdf]

    feedback_pdf_error = _collect_apply_result_feedback(
        {
            "updated_path": updated,
            "pdf_path": None,
            "pdf_error": "no pdf",
            "deduped": [{"action": "Ajouter au planning"}],
        },
        write_mag_central=True,
    )
    assert feedback_pdf_error["info_messages"] == []
    assert feedback_pdf_error["open_paths"] == [updated]
    assert feedback_pdf_error["warning_messages"] == ["PDF non généré automatiquement : no pdf"]


def test_build_notification_payloads_adds_paths_and_period():
    out = _build_notification_payloads(
        [{"be_num": "250001"}],
        updated_path="/tmp/planning.xlsx",
        pdf_path="/tmp/planning.pdf",
        week=4,
        year=2026,
    )
    assert len(out) == 1
    assert out[0]["planning_path"] == "/tmp/planning.xlsx"
    assert out[0]["planning_pdf_path"] == "/tmp/planning.pdf"
    assert out[0]["week"] == 4
    assert out[0]["year"] == 2026


def test_build_body_lines_multi_contains_all_action_sentences():
    out = _build_body_lines_multi(
        [{"action_sentence": "A1"}, {"action_sentence": "A2"}],
        week=4,
        year=2026,
    )
    assert out[0] == "Bonjour,"
    assert "Mise à jour du planning S04 - 2026 :" in out
    assert "A1" in out
    assert "A2" in out
    assert out[-1] == "Cordialement,"


def test_collect_benevole_emails_follows_action_rules():
    df_parambenev = pd.DataFrame(
        [
            {"Benevole": "ALICE", "Email": "alice@test.com"},
            {"Benevole": "BOB", "Email": "bob@test.com"},
        ]
    )
    payloads = [
        {
            "action": "Changement de date ou bénévole",
            "current_bene": "ALICE",
            "bene_choice": "BOB",
        },
        {
            "action": "Annulation",
            "current_bene": "ALICE",
            "bene_choice": "",
        },
    ]
    out = _collect_benevole_emails(payloads, df_parambenev)
    assert len(out) == 3
    assert set(out) == {"alice@test.com", "bob@test.com"}


def test_add_queue_item_validations(tmp_path):
    queue = [{"be_num": "250001"}]
    queue_item = {"be_num": "250002"}
    preview_path = tmp_path / "planning.xlsx"
    preview_path.touch()

    out, err = _add_queue_item(
        queue,
        queue_item,
        preview_path=preview_path,
        existing_queue_path=None,
    )
    assert err is None
    assert out == [{"be_num": "250001"}, {"be_num": "250002"}]

    out2, err2 = _add_queue_item(
        queue,
        queue_item,
        preview_path=tmp_path / "missing.xlsx",
        existing_queue_path=None,
    )
    assert out2 is None
    assert "Impossible de trouver le fichier planning" in str(err2)

    other = tmp_path / "other.xlsx"
    other.touch()
    out3, err3 = _add_queue_item(
        queue,
        queue_item,
        preview_path=preview_path,
        existing_queue_path=other,
    )
    assert out3 is None
    assert "contient un autre planning" in str(err3)


def test_clear_queue_state_keeps_or_clears_payloads():
    state = {
        "ship_update_queue": [{"be_num": "250001"}],
        "ship_update_queue_planning_path": "/tmp/a.xlsx",
        "ship_update_queue_week": 4,
        "ship_update_queue_year": 2026,
        "ship_update_payloads": [{"a": 1}],
    }
    _clear_queue_state(state, clear_payloads=False)
    assert state["ship_update_queue"] == []
    assert "ship_update_queue_planning_path" not in state
    assert "ship_update_queue_week" not in state
    assert "ship_update_queue_year" not in state
    assert state["ship_update_payloads"] == [{"a": 1}]

    _clear_queue_state(state, clear_payloads=True)
    assert "ship_update_payloads" not in state


def test_build_queue_dataframe_and_labels():
    queue = [
        {
            "be_num": "250001",
            "action": "Annulation",
            "dest_iata": "RUN",
            "date_new_long": "23 janvier 2026",
            "vol_display": "AF 652",
            "bene_short": "P DUPONT",
        }
    ]
    df = _build_queue_dataframe(queue)
    assert list(df.columns) == ["BE", "Action", "Destination", "Date", "Vol", "Bénévole"]
    assert df.iloc[0]["BE"] == "250001"
    labels = _build_queue_labels(queue)
    assert labels == ["1. RUN - BE 250001 - Annulation - 23 janvier 2026"]


def test_apply_queue_add_to_session_sets_metadata():
    state: dict[str, object] = {}
    queue = [{"be_num": "250001"}]
    _apply_queue_add_to_session(
        state,
        queue=queue,
        preview_path="/tmp/planning.xlsx",
        week=4,
        year=2026,
    )
    assert state["ship_update_queue"] == queue
    assert state["ship_update_queue_planning_path"] == "/tmp/planning.xlsx"
    assert state["ship_update_queue_week"] == 4
    assert state["ship_update_queue_year"] == 2026

    _apply_queue_add_to_session(
        state,
        queue=[],
        preview_path=None,
        week=5,
        year=2027,
    )
    assert state["ship_update_queue"] == []
    assert "ship_update_queue_planning_path" not in state
    assert state["ship_update_queue_week"] == 5
    assert state["ship_update_queue_year"] == 2027


def test_execute_queue_add_request_success_and_error(tmp_path):
    state: dict[str, object] = {}
    queue = [{"be_num": "250001"}]
    queue_item = {"be_num": "250002"}
    preview_path = tmp_path / "planning.xlsx"
    preview_path.touch()

    ok = _execute_queue_add_request(
        state,
        queue=queue,
        queue_item=queue_item,
        preview_path=preview_path,
        week=4,
        year=2026,
    )
    assert ok["error"] is None
    assert ok["message"] == "Modification ajoutée à la liste."
    assert len(ok["queue"]) == 2
    assert state["ship_update_queue_planning_path"] == str(preview_path)
    assert state["ship_update_queue_week"] == 4
    assert state["ship_update_queue_year"] == 2026

    ko = _execute_queue_add_request(
        state,
        queue=queue,
        queue_item=queue_item,
        preview_path=tmp_path / "missing.xlsx",
        week=4,
        year=2026,
    )
    assert "Impossible de trouver le fichier planning" in str(ko["error"])
    assert ko["message"] is None


def test_group_payloads_by_destination_and_expediteur():
    payloads = [
        {"dest_iata": "run", "action_sentence": "A", "expediteur": "HIA"},
        {"dest_label": "DLA", "action_sentence": "B", "expediteur": "ASF"},
        {"dest_iata": "RUN", "action_sentence": "C", "expediteur": "HIA"},
        {"dest_iata": "", "dest_label": "", "action_sentence": "D", "expediteur": "EXT"},
    ]
    by_dest = _group_payloads_by_destination(payloads)
    assert set(by_dest.keys()) == {"RUN", "DLA"}
    assert len(by_dest["RUN"]) == 2
    assert len(by_dest["DLA"]) == 1

    by_exp = _group_payloads_by_expediteur(payloads)
    assert set(by_exp.keys()) == {"HIA", "EXT"}
    assert len(by_exp["HIA"]) == 2
    assert len(by_exp["EXT"]) == 1


def test_dest_to_iata_maps_city_and_preserves_iata():
    df_paramdest = pd.DataFrame(
        [
            {"Dest_Ville": "Saint Denis", "Dest_IATA": "RUN"},
            {"Dest_Ville": "Douala", "Dest_IATA": "DLA"},
        ]
    )
    assert _dest_to_iata("Saint Denis", df_paramdest) == "RUN"
    assert _dest_to_iata("run", df_paramdest) == "RUN"
    assert _dest_to_iata("XYZ", df_paramdest) == "XYZ"


def test_build_planif_be_options_builds_labels_and_sorts():
    df_be_planif = pd.DataFrame(
        [
            {
                "Destination": "RUN",
                "BE_Numero": "250002",
                "BE_Nb_Colis": 1,
                "BE_Type": "MM",
                "Date_Vol": "2026-01-24",
            },
            {
                "Destination": "DLA",
                "BE_Numero": "250001",
                "BE_Nb_Colis": 2,
                "BE_Type": "FRET",
                "Date_Vol": "2026-01-23",
            },
        ]
    )
    out = _build_planif_be_options(df_be_planif, planned_set={"250001"})
    assert len(out) == 2
    assert out[0][0] == "DLA"
    assert out[0][1] == "250001"
    assert "(déjà au planning)" in out[0][2]
    assert "(non planifié)" in out[1][2]


def test_build_planifiable_selector_and_lookup_selector_data():
    df_be_planif = pd.DataFrame(
        [
            {"Destination": "DLA", "BE_Numero": "250001", "BE_Nb_Colis": 2, "BE_Type": "FRET", "Date_Vol": "2026-01-23"},
            {"Destination": "RUN", "BE_Numero": "250002", "BE_Nb_Colis": 1, "BE_Type": "MM", "Date_Vol": "2026-01-24"},
        ]
    )
    df_be_plan = pd.DataFrame([{"BE_Numero_Str": "250001"}])

    selector = _build_planifiable_be_selector_data(
        df_be_planif,
        df_be_plan,
        prefill_be="250002",
    )
    assert len(selector["options"]) == 2
    assert selector["values"] == ["250001", "250002"]
    assert selector["selected_idx"] == 1
    assert "(déjà au planning)" in selector["labels"][0]

    be_lookup = pd.DataFrame(
        [
            {"BE_Key": "250001", "Source": "planning"},
            {"BE_Key": "250002", "Source": "mag_central"},
        ]
    ).set_index("BE_Key")
    lookup_selector = _build_lookup_be_selector_data(be_lookup, prefill_be="250002")
    assert lookup_selector["options"] == ["250001", "250002"]
    assert lookup_selector["selected_idx"] == 1


def test_resolve_lookup_be_row_handles_series_dataframe_and_missing():
    be_lookup = pd.DataFrame(
        [
            {"BE_Key": "250001", "Source": "planning", "Val": 1},
            {"BE_Key": "250001", "Source": "mag_central", "Val": 2},
            {"BE_Key": "250002", "Source": "mag_central", "Val": 3},
        ]
    ).set_index("BE_Key")

    row, source = _resolve_lookup_be_row(be_lookup, selected_be="250001")
    assert row is not None
    assert row["Val"] == 1
    assert source == "planning"

    row2, source2 = _resolve_lookup_be_row(be_lookup, selected_be="250002")
    assert row2 is not None
    assert row2["Val"] == 3
    assert source2 == "mag_central"

    row_missing, source_missing = _resolve_lookup_be_row(be_lookup, selected_be="999999")
    assert row_missing is None
    assert source_missing == ""


def test_prepare_be_lookup_returns_reason_for_empty_and_missing_be():
    lookup, reason = _prepare_be_lookup(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert lookup.empty
    assert reason == "empty"

    df_missing = pd.DataFrame([{"BE_Numero_Str": "   "}])
    lookup2, reason2 = _prepare_be_lookup(df_missing, None, pd.DataFrame())
    assert lookup2.empty
    assert reason2 == "missing_be"


def test_prepare_be_lookup_prioritizes_non_zero_key_and_format_label():
    df_paramdest = pd.DataFrame([{"Dest_Ville": "Saint Denis", "Dest_IATA": "RUN"}])
    df_be_plan = pd.DataFrame(
        [
            {
                "BE_Numero_Str": "250001",
                "Destination": "Saint Denis",
                "Year": 2025,
                "Source": "planning",
                "_STATUS": "normal",
                "Date_Vol": "2025-01-10",
                "BE_Nb_Colis": 2,
                "BE_Type": "MM",
            }
        ]
    )
    df_be_d = pd.DataFrame(
        [
            {
                "BE_Numero_Str": "000001",
                "Destination": "RUN",
                "Year": 2025,
                "Source": "mag_central",
                "_STATUS": "normal",
                "Date_Vol": "2025-01-09",
                "BE_Nb_Colis": 1,
                "BE_Type": "FRET",
            }
        ]
    )
    lookup, reason = _prepare_be_lookup(df_be_plan, df_be_d, df_paramdest)
    assert reason is None
    assert list(lookup.index) == ["250001"]
    assert lookup.loc["250001", "Source"] == "planning"
    label = _format_be_option_label("250001", lookup)
    assert "RUN - BE 250001 - 2 colis - MM -" in label


def test_build_bene_meta_returns_expected_keys():
    df_parambenev = pd.DataFrame(
        [
            {
                "Benevole": "DUPONT",
                "ID": "42",
                "Telephone": "0600000000",
                "Prenom": "Paul",
                "Prenom_Court": "P",
                "Nom": "Dupont",
                "Email": "dupont@test.com",
            }
        ]
    )
    meta = _build_bene_meta(df_parambenev, "DUPONT")
    assert meta["Benevole"] == "DUPONT"
    assert meta["ID"] == "42"
    assert meta["Telephone"] == "0600000000"
    assert meta["Benevole_Prenom_Court"] == "P"
    assert meta["Benevole_Nom"] == "Dupont"
    assert meta["Email"] == "dupont@test.com"


def test_build_default_vol_tuple_prefill_and_fallback():
    out_prefill = _build_default_vol_tuple(
        prefill_date_new="2026-01-23",
        prefill_vol_new="AF652",
        prefill_heure_new="11:00",
        be_scope="Déjà au planning",
        date_initial="",
        current_vol="",
        current_heure="",
    )
    assert out_prefill == ("2026-01-23", "AF652", "11:00")

    out_planif = _build_default_vol_tuple(
        prefill_date_new=None,
        prefill_vol_new=None,
        prefill_heure_new=None,
        be_scope="A planifier",
        date_initial="2026-01-23",
        current_vol="AF652",
        current_heure="11:00",
    )
    assert out_planif == ("", "", "")

    out_existing = _build_default_vol_tuple(
        prefill_date_new=None,
        prefill_vol_new=None,
        prefill_heure_new=None,
        be_scope="Déjà au planning",
        date_initial="2026-01-23",
        current_vol="AF652",
        current_heure="11:00",
    )
    assert out_existing == ("2026-01-23", "AF652", "11:00")


def test_build_vol_selection_data_and_resolve_selected_vol():
    labels, values, idx = _build_vol_selection_data(
        [
            ("L1", ("d1", "v1", "h1")),
            ("L2", ("d2", "v2", "h2")),
        ],
        default_vol_tuple=("d2", "v2", "h2"),
    )
    assert labels == ["L1", "L2"]
    assert values == [("d1", "v1", "h1"), ("d2", "v2", "h2")]
    assert idx == 1
    assert _resolve_selected_vol(labels, values, "L2") == ("d2", "v2", "h2")
    assert _resolve_selected_vol(labels, values, "unknown") == ("d1", "v1", "h1")

    labels2, values2, idx2 = _build_vol_selection_data([], default_vol_tuple=("x", "y", "z"))
    assert labels2 == ["Aucun vol disponible"]
    assert values2 == [("", "", "")]
    assert idx2 == 0


def test_build_bene_options_and_default_label():
    df_parambenev = pd.DataFrame([{"Benevole": "ALICE"}, {"Benevole": "BOB"}])

    def status_for(name):
        return "disponible" if name == "ALICE" else "indisponible"

    out_planif = _build_bene_options(df_parambenev, be_scope="A planifier", status_for=status_for)
    assert out_planif == ["ALICE", "BOB"]

    out_existing = _build_bene_options(
        df_parambenev,
        be_scope="Déjà au planning",
        status_for=status_for,
    )
    assert out_existing == ["ALICE (disponible)", "BOB (indisponible)"]

    d1 = _build_default_bene_label(
        prefill_bene="ALICE",
        current_bene="BOB",
        be_scope="Déjà au planning",
        status_for=status_for,
    )
    assert d1 == "ALICE (disponible)"

    d2 = _build_default_bene_label(
        prefill_bene=None,
        current_bene="BOB",
        be_scope="A planifier",
        status_for=status_for,
    )
    assert d2 == "BOB"


def test_extract_bene_choice_and_fill_bene_name():
    assert _extract_bene_choice("ALICE (disponible)", ["ALICE (disponible)"]) == "ALICE"
    assert _extract_bene_choice("Aucun bénévole disponible", []) == ""

    df_parambenev = pd.DataFrame([{"Benevole": "ALICE", "Prenom_Court": "A", "Nom": "Alice"}])
    prenom, nom = _fill_bene_name_from_parambenev(
        df_parambenev,
        bene_choice="ALICE",
        bene_prenom_court="",
        bene_nom="",
    )
    assert prenom == "A"
    assert nom == "Alice"

    prenom2, nom2 = _fill_bene_name_from_parambenev(
        df_parambenev,
        bene_choice="ALICE",
        bene_prenom_court="X",
        bene_nom="Y",
    )
    assert prenom2 == "X"
    assert nom2 == "Y"


def test_prepare_dispo_parses_date_and_time_columns():
    df = pd.DataFrame(
        [
            {
                "Benevole": "ALICE",
                "Date": "23/01/2026",
                "Heure_Arrivee": "10:00",
                "Heure_Depart": "12:30",
            }
        ]
    )
    out = _prepare_dispo(df)
    assert str(out.loc[0, "Date"]) == "2026-01-23"
    assert str(out.loc[0, "Arr"]) == "10:00:00"
    assert str(out.loc[0, "Dep"]) == "12:30:00"


def test_resolve_assignment_from_plan_row_and_bene_identity():
    plan_row = pd.Series(
        {
            "Date_Vol": "2026-01-24",
            "Numero_Vol": "AF652",
            "Heure_Vol": "11:00",
            "Benevole": "ALICE",
            "Benevole_Prenom_Court": "A",
            "Benevole_Nom": "Dupont",
        }
    )
    ctx = _resolve_assignment_from_plan_row(
        plan_row=plan_row,
        date_initial="2026-01-23",
    )
    assert ctx["date_initial"] == "2026-01-24"
    assert ctx["current_vol"] == "AF652"
    assert ctx["current_heure"] == "11:00"
    assert ctx["current_bene"] == "ALICE"
    assert ctx["bene_prenom_court"] == "A"
    assert ctx["bene_nom"] == "Dupont"

    df_parambenev = pd.DataFrame(
        [{"Benevole": "ALICE", "Prenom_Court": "AL", "Nom": "Alice"}]
    )
    prenom, nom = _resolve_current_bene_identity(
        df_parambenev,
        current_bene="ALICE",
        bene_prenom_court="",
        bene_nom="",
    )
    assert prenom == "AL"
    assert nom == "Alice"


def test_build_assignment_summary_formats_sentence_with_fallbacks():
    out = _build_assignment_summary(
        selected_be="250001",
        dest_iata="RUN",
        date_initial="2026-01-23",
        date_new="2026-01-24",
        vol_new="AF652",
        current_vol="",
        bene_prenom_court="P",
        bene_nom="Dupont",
        bene_choice="",
        action_choice="Changement de date ou bénévole",
    )
    assert out["date_initial_long"] != ""
    assert out["date_new_long"] != ""
    assert out["vol_disp"] == "AF 652"
    assert out["bene_short"] == "P DUPONT"
    assert "sera reprogrammé" in out["action_sentence"]

    out_fallback = _build_assignment_summary(
        selected_be="250001",
        dest_iata="RUN",
        date_initial="2026-01-23",
        date_new="2026-01-23",
        vol_new="",
        current_vol="",
        bene_prenom_court="",
        bene_nom="",
        bene_choice="",
        action_choice="Annulation",
    )
    assert "(vol ?)" not in out_fallback["action_sentence"]
    assert "sera annulé" in out_fallback["action_sentence"]


def test_coerce_display_types_forces_phone_like_columns_to_str():
    df = pd.DataFrame(
        [{"Telephone": 600000000, "Phone Main": 123456789, "Other": 42}]
    )
    out = _coerce_display_types(df)
    assert out["Telephone"].iloc[0] == "600000000"
    assert out["Phone Main"].iloc[0] == "123456789"
    assert out["Other"].iloc[0] == 42


def test_weeks_from_status_df_and_selector_data():
    df_status = pd.DataFrame(
        [
            {"Week": 4, "Year": 2026},
            {"Week": 1, "Year": 2026},
            {"Week": 52, "Year": 2025},
        ]
    )
    weeks_set = _weeks_from_status_df(df_status)
    weeks, labels, week_map = _build_week_selector_data(weeks_set)

    assert weeks == [(4, 2026), (1, 2026), (52, 2025)]
    assert labels[0] == "2026 - Semaine 04"
    assert week_map["2026 - Semaine 01"] == (1, 2026)
    assert _weeks_from_status_df(pd.DataFrame()) == set()


def test_build_planning_version_choices_builds_labels_and_map():
    candidates = [
        "ASFmm - PLANNING SEMAINE 2026-04-02.xlsx",
        "ASFmm - PLANNING SEMAINE 2026-04-01.xlsx",
    ]

    def _fake_parse(path):
        return (2, 0) if path.name.endswith("-02.xlsx") else (1, 0)

    labels, path_map = _build_planning_version_choices(
        candidates,
        parse_version_from_name=_fake_parse,
    )
    assert labels[0].startswith("v2")
    assert "ASFmm - PLANNING SEMAINE 2026-04-02.xlsx" in labels[0]
    assert path_map[labels[1]] == candidates[1]


def test_format_preview_dataframe_formats_date_time_and_phone_columns():
    df_preview = pd.DataFrame(
        [
            {
                "Date_Vol": pd.Timestamp("2026-01-23"),
                "Heure_Vol": pd.Timestamp("2026-01-23 11:30:00").time(),
                "Telephone": 600000000,
                "Other": 42,
            }
        ]
    )
    out = _format_preview_dataframe(df_preview)

    assert out.loc[0, "Date_Vol"] == "23/01/26"
    assert out.loc[0, "Heure_Vol"] == "11h30"
    assert out.loc[0, "Telephone"] == "600000000"
    assert out.loc[0, "Other"] == 42


def test_open_file_in_os_dispatch_and_errors():
    popen_calls: list[list[str]] = []
    start_calls: list[str] = []

    def fake_popen(cmd: list[str]):
        popen_calls.append(cmd)
        return None

    def fake_start(path: str):
        start_calls.append(path)

    assert (
        _open_file_in_os(
            "/tmp/file.xlsx",
            platform_system_fn=lambda: "Darwin",
            popen_fn=fake_popen,
        )
        is True
    )
    assert popen_calls[-1] == ["open", "/tmp/file.xlsx"]

    assert (
        _open_file_in_os(
            "C:/tmp/file.xlsx",
            platform_system_fn=lambda: "Windows",
            startfile_fn=fake_start,
            popen_fn=fake_popen,
        )
        is True
    )
    assert start_calls == ["C:/tmp/file.xlsx"]

    assert (
        _open_file_in_os(
            "/tmp/file.pdf",
            platform_system_fn=lambda: "Linux",
            popen_fn=fake_popen,
        )
        is True
    )
    assert popen_calls[-1] == ["xdg-open", "/tmp/file.pdf"]

    def failing_popen(_cmd: list[str]):
        raise RuntimeError("boom")

    assert (
        _open_file_in_os(
            "/tmp/file.xlsx",
            platform_system_fn=lambda: "Darwin",
            popen_fn=failing_popen,
        )
        is False
    )
    assert _open_file_in_os("", platform_system_fn=lambda: "Linux") is False
    assert _open_file_in_os(None, platform_system_fn=lambda: "Linux") is False


def test_load_export_planning_sheet_and_select_source_for_be(tmp_path):
    path = tmp_path / "planning.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([{"A": 1}]).to_excel(writer, sheet_name="Export planning", index=False)
        pd.DataFrame([{"B": 2}]).to_excel(writer, sheet_name="Other", index=False)

    loaded = _load_export_planning_sheet(path)
    assert loaded is not None
    assert list(loaded.columns) == ["A"]

    preview = pd.DataFrame([{"X": 9}])
    selected = _select_source_for_be(loaded, preview)
    assert selected is not None
    assert list(selected.columns) == ["A"]

    selected_fallback = _select_source_for_be(pd.DataFrame(), preview)
    assert selected_fallback is preview

    assert _load_export_planning_sheet(tmp_path / "missing.xlsx") is None


def test_load_be_sources_for_week_uses_export_planning_and_status_loader(tmp_path):
    path = tmp_path / "planning.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(
            [
                {
                    "BE_Numero": "260001",
                    "Destination": "RUN",
                    "Date_Vol": "23/01/26",
                    "Vol": "AF652",
                    "Heure_Vol": "18:20",
                }
            ]
        ).to_excel(writer, sheet_name="Export planning", index=False)

    captured: dict[str, object] = {}

    def _fake_status_loader(week, year, *, tdb_path):
        captured["week"] = week
        captured["year"] = year
        captured["tdb_path"] = tdb_path
        return pd.DataFrame([{"BE_Numero_Str": "260002"}])

    out = _load_be_sources_for_week(
        preview_path=path,
        df_preview=pd.DataFrame(),
        selected_week=4,
        selected_year=2026,
        tdb_path="/tmp/tdb.xlsx",
        load_be_status_d_for_week_fn=_fake_status_loader,
    )
    assert captured == {"week": 4, "year": 2026, "tdb_path": "/tmp/tdb.xlsx"}
    assert len(out["df_be_plan"]) == 1
    assert out["df_be_plan"].iloc[0]["BE_Numero_Str"] == "260001"
    assert len(out["df_be_d"]) == 1
    assert out["df_be_d"].iloc[0]["BE_Numero_Str"] == "260002"


def test_bene_status_handles_already_assigned_available_unknown_and_outside():
    df_dispo = pd.DataFrame(
        [
            {
                "Benevole": "ALICE",
                "Date": pd.Timestamp("2026-01-23").date(),
                "Arr": pd.Timestamp("10:00").time(),
                "Dep": pd.Timestamp("12:00").time(),
            },
            {
                "Benevole": "BOB",
                "Date": pd.Timestamp("2026-01-23").date(),
                "Arr": None,
                "Dep": None,
            },
        ]
    )
    df_planning = pd.DataFrame(
        [
            {
                "Benevole": "ALICE",
                "Date_Vol": "2026-01-23",
                "Numero_Vol": "AF652",
            }
        ]
    )

    assert (
        _bene_status(
            df_dispo,
            df_planning,
            "ALICE",
            "2026-01-23",
            "11:00",
            "AF652",
        )
        == "déjà affecté sur ce créneau"
    )
    assert (
        _bene_status(df_dispo, pd.DataFrame(), "ALICE", "2026-01-23", "11:00", "AF652")
        == "disponible"
    )
    assert (
        _bene_status(df_dispo, pd.DataFrame(), "ALICE", "2026-01-23", "13:00", "AF652")
        == "indisponible"
    )
    assert (
        _bene_status(df_dispo, pd.DataFrame(), "BOB", "2026-01-23", "11:00", "AF652")
        == "inconnu"
    )
    assert (
        _bene_status(df_dispo, pd.DataFrame(), "ALICE", "invalid", "11:00", "AF652")
        == "indisponible"
    )


def test_collect_be_from_planning_filters_week_and_keeps_fields():
    df = pd.DataFrame(
        [
            {
                "BE_Numero": "250001.0",
                "Destination": "RUN",
                "Date_Vol": "23/01/26",
                "Vol": "AF652",
                "Heure_Vol": "18:20",
                "BE_Nb_Colis": 4,
                "BE_Type": "MM",
                "_STATUS": "new",
            },
            {
                "BE_Numero": "250002",
                "Destination": "RUN",
                "Date_Vol": "30/12/25",
                "Vol": "AF650",
                "Heure_Vol": "09:00",
                "BE_Nb_Colis": 2,
                "BE_Type": "FRET",
            },
        ]
    )
    out = _collect_be_from_planning(df, week=4, year=2026)
    assert len(out) == 1
    assert out.iloc[0]["BE_Numero_Str"] == "250001"
    assert out.iloc[0]["Numero_Vol"] == "AF652"
    assert out.iloc[0]["Heure_Vol"] == "18:20"
    assert out.iloc[0]["BE_Nb_Colis"] == 4
    assert out.iloc[0]["BE_Type"] == "MM"
    assert out.iloc[0]["_STATUS"] == "new"
    assert out.iloc[0]["Source"] == "planning"


def test_find_row_in_df_matches_be_suffix():
    df = pd.DataFrame(
        [
            {"BE Numéro": "240999.0", "Other": "x"},
            {"BE_NUMERO": "250001", "Other": "y"},
        ]
    )
    row = _find_row_in_df(df, "0001")
    assert row is not None
    assert row["Other"] == "y"


def test_pop_prefill_values_handles_dict_and_non_dict():
    state = {
        "ship_update_prefill": {
            "action": "Annulation",
            "be_key": "250001",
            "be_num": "250001",
            "date_new": "2026-01-23",
            "vol_new": "AF652",
            "heure_new": "11:00",
            "bene_choice": "ALICE",
            "be_scope": "Déjà au planning",
        }
    }
    out = _pop_prefill_values(state)
    assert out["action"] == "Annulation"
    assert out["be_key"] == "250001"
    assert "ship_update_prefill" not in state

    state2 = {"ship_update_prefill": "invalid"}
    out2 = _pop_prefill_values(state2)
    assert out2["action"] is None
    assert out2["be_scope"] is None


def test_build_queue_item_maps_expected_payload():
    be_row = pd.Series({"BE_Numero_Str": "250001", "Destination": "RUN"})
    plan_row_full = pd.Series({"BE_NUMERO": "250001", "Some": "value"})
    out = _build_queue_item(
        week=4,
        year=2026,
        dest_iata="RUN",
        dest_label="RUN",
        selected_be="250001",
        be_scope="Déjà au planning",
        date_initial_long="23 janvier 2026",
        date_new_long="24 janvier 2026",
        vol_disp="AF 652",
        bene_short="P DUPONT",
        expediteur_name="HIA",
        action_choice="Changement de date ou bénévole",
        action_sentence="Action sentence",
        be_source="planning",
        preview_path="/tmp/planning.xlsx",
        be_row=be_row,
        date_new="2026-01-24",
        vol_new="AF652",
        heure_new="11:00",
        bene_choice="DUPONT",
        current_bene="MARTIN",
        plan_row_full=plan_row_full,
        bene_meta={"ID": "42"},
        bene_changed=True,
    )
    assert out["week"] == 4
    assert out["year"] == 2026
    assert out["be_num"] == "250001"
    assert out["planning_path"] == "/tmp/planning.xlsx"
    assert out["be_info"]["BE_Numero_Str"] == "250001"
    assert out["plan_row_full"]["BE_NUMERO"] == "250001"
    assert out["bene_choice"] == "DUPONT"
    assert out["bene_changed"] is True


def test_notification_period_from_payloads_defaults_and_overrides():
    week, year = _notification_period_from_payloads(
        [],
        default_week=4,
        default_year=2026,
    )
    assert (week, year) == (4, 2026)

    week2, year2 = _notification_period_from_payloads(
        [{"week": "5", "year": "2027"}],
        default_week=4,
        default_year=2026,
    )
    assert (week2, year2) == (5, 2027)

    week3, year3 = _notification_period_from_payloads(
        [{"week": "x", "year": "y"}],
        default_week=4,
        default_year=2026,
    )
    assert (week3, year3) == (4, 2026)


def test_resolve_planning_version_major_uses_parser_and_fallback():
    def parse_ok(_path):
        return (7, 0)

    def parse_ko(_path):
        raise ValueError("boom")

    assert (
        _resolve_planning_version_major(
            "/tmp/planning.xlsx",
            parse_version_from_name=parse_ok,
        )
        == 7
    )
    assert (
        _resolve_planning_version_major(
            "/tmp/planning.xlsx",
            parse_version_from_name=parse_ko,
        )
        == 1
    )
    assert (
        _resolve_planning_version_major(
            "",
            parse_version_from_name=parse_ok,
        )
        == 1
    )


def test_resolve_notification_pdf_path_prefers_payload_then_sidecar_then_export(tmp_path):
    planning = tmp_path / "planning.xlsx"
    planning.touch()
    payload_pdf = tmp_path / "payload.pdf"
    payload_pdf.touch()

    out_payload = _resolve_notification_pdf_path(str(planning), str(payload_pdf))
    assert out_payload == str(payload_pdf)

    missing_payload = tmp_path / "missing.pdf"
    sidecar = tmp_path / "planning.pdf"
    sidecar.touch()
    out_sidecar = _resolve_notification_pdf_path(str(planning), str(missing_payload))
    assert out_sidecar == str(sidecar)

    sidecar.unlink()
    out_export = _resolve_notification_pdf_path(
        str(planning),
        "",
        export_pdf_fn=lambda _p: tmp_path / "generated.pdf",
    )
    assert out_export == str(tmp_path / "generated.pdf")


def test_build_asf_notification_draft_builds_expected_fields(tmp_path):
    planning = tmp_path / "planning.xlsx"
    planning.touch()
    sidecar = tmp_path / "planning.pdf"
    sidecar.touch()
    payloads = [
        {
            "action_sentence": "A1",
            "week": 4,
            "year": 2026,
            "planning_path": str(planning),
            "planning_pdf_path": "",
        }
    ]
    draft = _build_asf_notification_draft(
        payloads,
        ["a@test.com", "A@test.com", ""],
        default_week=1,
        default_year=2000,
        parse_version_from_name=lambda _p: (3, 0),
        export_pdf_fn=None,
    )
    assert draft["week"] == 4
    assert draft["year"] == 2026
    assert draft["subject"] == "MAJ Planning S04-03"
    assert draft["to_list"][0] == "messmed@aviation-sans-frontieres-fr.org"
    assert draft["to_list"][1:] == ["a@test.com"]
    assert draft["attachments"] == [str(sidecar)]
    assert "Mise à jour du planning S04 - 2026" in draft["body_html"]


def test_build_destination_notification_drafts_formats_and_filters():
    payloads = [
        {"dest_iata": "RUN", "action_sentence": "A1"},
        {"dest_label": "DLA", "action_sentence": "A2"},
    ]

    def fake_get(_df, dest):
        if dest == "RUN":
            return "run@test.com", "cc@test.com"
        return "", ""

    drafts = _build_destination_notification_drafts(
        payloads,
        pd.DataFrame(),
        week=4,
        year=2026,
        get_emails_for_destination=fake_get,
    )
    assert len(drafts) == 1
    assert drafts[0]["name"] == "RUN"
    assert drafts[0]["to_list"] == ["run@test.com"]
    assert drafts[0]["cc_list"] == ["cc@test.com", "messmed@aviation-sans-frontieres-fr.org"]
    assert drafts[0]["subject"] == "MAJ Planning S04 - RUN"
    assert "A1" in drafts[0]["body_html"]


def test_build_expediteur_notification_drafts_formats_and_filters():
    payloads = [
        {"expediteur": "HIA", "action_sentence": "A1"},
        {"expediteur": "ASF", "action_sentence": "A2"},
        {"expediteur": "EXT", "action_sentence": "A3"},
    ]

    def fake_get(_df, exp):
        if exp == "HIA":
            return "hia@test.com", ""
        return "", ""

    drafts = _build_expediteur_notification_drafts(
        payloads,
        pd.DataFrame(),
        week=4,
        year=2026,
        get_emails_for_expediteur=fake_get,
    )
    assert len(drafts) == 1
    assert drafts[0]["name"] == "HIA"
    assert drafts[0]["to_list"] == ["hia@test.com"]
    assert drafts[0]["cc_list"] == ["messmed@aviation-sans-frontieres-fr.org"]
    assert drafts[0]["subject"] == "HIA - MAJ Planning S04"
    assert "A1" in drafts[0]["body_html"]


def test_prepare_notification_context_and_send_helpers(tmp_path):
    planning = tmp_path / "planning.xlsx"
    planning.touch()
    payloads = [
        {
            "dest_iata": "RUN",
            "expediteur": "HIA",
            "action_sentence": "A1",
            "week": 4,
            "year": 2026,
            "planning_path": str(planning),
            "planning_pdf_path": "",
            "bene_choice": "ALICE",
            "current_bene": "",
            "action": "Ajouter au planning",
        }
    ]
    df_parambenev = pd.DataFrame([{"Benevole": "ALICE", "Email": "alice@test.com"}])

    def _get_dest(_df, dest):
        return ("dest@test.com", "destcc@test.com") if dest == "RUN" else ("", "")

    def _get_exp(_df, exp):
        return ("exp@test.com", "") if exp == "HIA" else ("", "")

    context = _prepare_notification_context(
        payloads,
        default_week=1,
        default_year=2000,
        df_parambenev=df_parambenev,
        df_paramdest=pd.DataFrame(),
        df_paramexpediteur=pd.DataFrame(),
        parse_version_from_name=lambda _p: (2, 0),
        export_pdf_fn=None,
        get_emails_for_destination=_get_dest,
        get_emails_for_expediteur=_get_exp,
    )
    assert context["week"] == 4
    assert context["year"] == 2026
    assert context["asf_draft"]["subject"] == "MAJ Planning S04-02"
    assert len(context["dest_drafts"]) == 1
    assert len(context["exp_drafts"]) == 1

    calls: list[dict] = []

    def _fake_outlook(**kwargs):
        calls.append(kwargs)

    _send_outlook_draft(
        context["asf_draft"],
        create_outlook_draft_fn=_fake_outlook,
    )
    sent_dest = _send_named_outlook_drafts(
        context["dest_drafts"],
        create_outlook_draft_fn=_fake_outlook,
    )
    assert len(calls) == 2
    assert calls[0]["use_signature"] is True
    assert sent_dest == ["RUN"]

    level_ok, msg_ok = _build_sent_drafts_feedback(
        sent_dest,
        success_prefix="Brouillons Escale ouverts :",
        empty_message="Aucun email ParamDest trouvé.",
    )
    assert level_ok == "success"
    assert "RUN" in msg_ok

    level_empty, msg_empty = _build_sent_drafts_feedback(
        [],
        success_prefix="Brouillons Expéditeur ouverts :",
        empty_message="Aucun email expéditeur trouvé (ou expéditeur ASF).",
    )
    assert level_empty == "warning"
    assert "Aucun email expéditeur" in msg_empty


def test_send_named_outlook_drafts_with_feedback_variants():
    calls: list[dict] = []

    def _fake_outlook(**kwargs):
        calls.append(kwargs)

    level_ok, message_ok = _send_named_outlook_drafts_with_feedback(
        [
            {"name": "RUN", "to_list": ["dest@test.com"], "cc_list": [], "subject": "s", "body_html": "b", "attachments": None},
            {"name": "DLA", "to_list": ["dest2@test.com"], "cc_list": [], "subject": "s2", "body_html": "b2", "attachments": None},
        ],
        create_outlook_draft_fn=_fake_outlook,
        success_prefix="Brouillons Escale ouverts :",
        empty_message="Aucun email ParamDest trouvé.",
    )
    assert level_ok == "success"
    assert "RUN" in message_ok and "DLA" in message_ok
    assert len(calls) == 2

    level_empty, message_empty = _send_named_outlook_drafts_with_feedback(
        [],
        create_outlook_draft_fn=_fake_outlook,
        success_prefix="Brouillons Expéditeur ouverts :",
        empty_message="Aucun email expéditeur trouvé (ou expéditeur ASF).",
    )
    assert level_empty == "warning"
    assert "Aucun email expéditeur" in message_empty


def test_basic_formatters_and_numeric_coercion_branches(monkeypatch):
    assert sh._fmt_date_long("") == ""
    monkeypatch.setattr(sh, "format_time_value", lambda *_a, **_k: None)
    assert sh._fmt_time("11h00") == "11h00"

    monkeypatch.setattr(sh.pd, "isna", lambda _v: (_ for _ in ()).throw(TypeError("boom")))
    assert sh._coerce_int("bad", 7) == 7
    assert sh._coerce_int("12.0", 0) == 12
    assert sh._coerce_int("not-a-number", 9) == 9


def test_selection_and_bene_label_helpers_edge_cases():
    assert _resolve_selected_vol([], [], "x") == ("", "", "")
    assert _build_bene_options(pd.DataFrame(), be_scope="A planifier", status_for=lambda _n: "ok") == []
    assert _build_default_bene_label(
        prefill_bene="ALICE",
        current_bene="",
        be_scope="A planifier",
        status_for=lambda _n: "disponible",
    ) == "ALICE"
    assert _build_default_bene_label(
        prefill_bene=None,
        current_bene="ALICE",
        be_scope="Planning",
        status_for=lambda _n: "disponible",
    ) == "ALICE (disponible)"


def test_fill_bene_name_from_parambenev_handles_empty_missing_and_errors():
    out = _fill_bene_name_from_parambenev(
        None,
        bene_choice="ALICE",
        bene_prenom_court="",
        bene_nom="",
    )
    assert out == ("", "")

    df = pd.DataFrame([{"Benevole": "BOB", "Prenom_Court": "B.", "Nom": "MARTIN"}])
    out_missing = _fill_bene_name_from_parambenev(
        df,
        bene_choice="ALICE",
        bene_prenom_court="",
        bene_nom="",
    )
    assert out_missing == ("", "")

    class _BadDf(pd.DataFrame):
        @property
        def _constructor(self):  # pragma: no cover
            return _BadDf

        @property
        def empty(self):
            raise TypeError("boom")

    out_error = _fill_bene_name_from_parambenev(
        _BadDf([{"Benevole": "ALICE"}]),
        bene_choice="ALICE",
        bene_prenom_court="P",
        bene_nom="N",
    )
    assert out_error == ("P", "N")


def test_queue_open_and_notification_email_helpers_branches(tmp_path):
    queue, err = _add_queue_item([], {}, preview_path=None, existing_queue_path=None)
    assert queue is None
    assert "Impossible de trouver le fichier planning" in str(err)

    assert _open_file_in_os("   ") is False
    assert _open_file_in_os(
        "x",
        platform_system_fn=lambda: "Windows",
        startfile_fn=None,
        popen_fn=lambda _args: None,
    ) is False

    payloads = [
        {"action": "Ajouter au planning", "bene_choice": "ALICE"},
        {"action": "Changement de date ou bénévole", "current_bene": "ALICE", "bene_choice": "BOB"},
    ]
    mails = _collect_benevole_emails(
        payloads,
        pd.DataFrame([{"Benevole": "ALICE", "Email": "alice@test.com"}]),
    )
    assert mails == ["alice@test.com", "alice@test.com"]

    planning = tmp_path / "planning.xlsx"
    planning.write_text("x", encoding="utf-8")
    pdf = _resolve_notification_pdf_path(
        planning,
        "",
        export_pdf_fn=lambda _p: (_ for _ in ()).throw(RuntimeError("pdf err")),
    )
    assert pdf == ""


def test_be_key_dest_and_planifiable_selector_helpers(monkeypatch):
    assert _normalize_be_key_for_select("", year=2026) == ""
    monkeypatch.setattr(sh.pd, "isna", lambda _v: (_ for _ in ()).throw(TypeError("boom")))
    assert _normalize_be_key_for_select("001234", year="bad") == "001234"

    class _BadParam(pd.DataFrame):
        @property
        def _constructor(self):  # pragma: no cover
            return _BadParam

        def dropna(self, *args, **kwargs):
            raise KeyError("boom")

    assert _dest_to_iata("douala", _BadParam()) == "DOUALA"
    assert _build_planif_be_options(pd.DataFrame(), set()) == []

    selector = _build_planifiable_be_selector_data(None, None, prefill_be=None)
    assert selector["options"] == []
    assert selector["labels"] == []
    assert selector["values"] == []


def test_prepare_lookup_and_format_helpers_cover_status_and_fallbacks():
    df_status = pd.DataFrame(
        [
            {"BE_Numero_Str": "250001", "Destination": "DLA", "Source": "planning", "_STATUS": "new"},
            {"BE_Numero_Str": "250002", "Destination": "RUN", "Source": "mag", "_STATUS": "old"},
            {"BE_Numero_Str": "250003", "Destination": "ABJ", "Source": "mag", "_STATUS": "orig"},
            {"BE_Numero_Str": "250004", "Destination": "CKY", "Source": "mag", "_STATUS": "weird"},
            {"BE_Numero_Str": "250005", "Destination": "DLA", "Source": "mag", "_STATUS": ""},
        ]
    )
    lookup, err = _prepare_be_lookup(
        df_status,
        None,
        pd.DataFrame([{"Dest_IATA": "DLA", "Dest_Ville": "DOUALA"}]),
    )
    assert err is None
    assert not lookup.empty

    dup = pd.concat([lookup.iloc[[0]], lookup.iloc[[0]]], ignore_index=False)
    label = _format_be_option_label(str(dup.index[0]), dup)
    assert "BE" in label
    assert _format_be_option_label("999999", lookup) == "999999"

    assert _coerce_display_types(pd.DataFrame()).empty
    assert _weeks_from_status_df(pd.DataFrame([{"week": 1, "year": 2026}])) == set()
    weeks = _weeks_from_status_df(pd.DataFrame([{"Week": "x", "Year": "bad"}]))
    assert weeks == set()

    formatted = _format_preview_dataframe(
        pd.DataFrame(
            [
                {
                    "Date": pd.Timestamp("2026-01-20"),
                    "Heure": dt.time(11, 30),
                }
            ]
        )
    )
    assert formatted.iloc[0]["Date"] == "20/01/26"
    assert formatted.iloc[0]["Heure"] == "11h30"


def test_load_collect_and_find_helpers_edge_paths(tmp_path, monkeypatch):
    assert _load_export_planning_sheet(None) is None

    fake = tmp_path / "planning.xlsx"
    fake.write_text("x", encoding="utf-8")
    monkeypatch.setattr(sh.pd, "read_excel", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("boom")))
    assert _load_export_planning_sheet(fake) is None

    assert _bene_status(pd.DataFrame(), pd.DataFrame(), "ALICE", "bad-date", "bad-time") == "indisponible"
    assert _collect_be_from_planning(pd.DataFrame(), week=4, year=2026).empty
    assert _collect_be_from_planning(pd.DataFrame([{"Date_Vol": "20/01/26"}]), week=4, year=2026).empty
    assert _find_row_in_df(pd.DataFrame(), "250001") is None
    assert _find_row_in_df(pd.DataFrame([{"BE_Numero": "260001"}]), "999999") is None
