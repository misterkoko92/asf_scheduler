# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pandas as pd

import scheduler.config_paths as cp
from asf_app.services.planning_exports_service import (
    available_weeks_from_exports,
    find_planning_files_for_week,
    load_planning_preview,
    load_planning_preview_with_path,
    load_planning_xlsx,
    parse_version_from_name,
)


def test_parse_version_from_name():
    assert parse_version_from_name(Path("ASFmm - PLANNING SEMAINE 2026-05-03.xlsx")) == (3, 0)
    assert parse_version_from_name(Path("ASFmm - PLANNING SEMAINE N° 05 - 2026 v12-2.xlsx")) == (12, 2)
    assert parse_version_from_name(Path("planning_sans_version.xlsx")) == (1, 0)


def test_available_weeks_from_exports_local(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base_dir = root / "Planning MAB" / "ASFmm PLANNING 2026"
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "ASFmm - PLANNING SEMAINE 2026-02-01.xlsx").touch()

    monkeypatch.setattr(cp, "ASF_ONEDRIVE", root)
    monkeypatch.setattr(cp, "is_graph_onedrive", lambda: False)

    weeks = available_weeks_from_exports()
    assert (2, 2026) in weeks


def test_find_planning_files_for_week_sorted(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base_dir = root / "Planning MAB" / "ASFmm PLANNING 2026"
    base_dir.mkdir(parents=True, exist_ok=True)
    files = [
        base_dir / "ASFmm - PLANNING SEMAINE 2026-05-01.xlsx",
        base_dir / "ASFmm - PLANNING SEMAINE 2026-05-03.xlsx",
        base_dir / "ASFmm - PLANNING SEMAINE 2026-05-02.xlsx",
    ]
    for f in files:
        f.touch()

    monkeypatch.setattr(cp, "ASF_ONEDRIVE", root)
    monkeypatch.setattr(cp, "is_graph_onedrive", lambda: False)

    results = find_planning_files_for_week(5, 2026)
    assert [Path(p).name for p in results[:3]] == [
        "ASFmm - PLANNING SEMAINE 2026-05-03.xlsx",
        "ASFmm - PLANNING SEMAINE 2026-05-02.xlsx",
        "ASFmm - PLANNING SEMAINE 2026-05-01.xlsx",
    ]


def test_load_planning_preview_with_path(tmp_path, monkeypatch):
    path = tmp_path / "planning.xlsx"
    df = pd.DataFrame({"A": [1], "B": [2]})
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="Export planning", index=False)

    monkeypatch.setattr(cp, "is_graph_onedrive", lambda: False)

    df_out, msg, used_path = load_planning_preview_with_path(2, 2026, path)
    assert used_path == path
    assert df_out is not None and not df_out.empty
    assert "Export planning" in msg


def test_load_planning_xlsx_parses(tmp_path):
    from openpyxl import Workbook

    path = tmp_path / "planning.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Planning"
    row = [
        "",
        "",
        "Lundi 01/01",
        "Jean Dupont",
        "",
        "BRAZZAVILLE",
        "BZV",
        "CDG-BZV",
        "AF123",
        "10:00",
        "250001",
        2,
        "MM",
        "",
        "",
        "ASF",
        "Hopital",
    ]
    ws.append(row)
    wb.save(path)

    df = load_planning_xlsx(path, default_year=2025)
    assert not df.empty
    assert df.iloc[0]["be"] == "250001"


def test_available_weeks_from_exports_graph_mode(monkeypatch):
    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        cp,
        "list_onedrive_files",
        lambda *args, **kwargs: [
            {"name": "ASFmm - PLANNING SEMAINE 2026-06-01.xlsx"},
            {"name": "ASFmm - PLANNING SEMAINE N° 07 - 2026 v2.xlsx"},
            {"name": "noise.txt"},
        ],
    )
    weeks = available_weeks_from_exports()
    assert (6, 2026) in weeks
    assert (7, 2026) in weeks


def test_find_planning_files_for_week_graph_mode_sorted(monkeypatch):
    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: True)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_output_remote_dir", lambda year: f"Planning/{year}")
    monkeypatch.setattr(
        cp,
        "list_onedrive_files",
        lambda *args, **kwargs: [
            {"name": "ASFmm - PLANNING SEMAINE 2026-05-01.xlsx", "path": "Planning/2026/v1.xlsx"},
            {"name": "ASFmm - PLANNING SEMAINE 2026-05-03.xlsx", "path": "Planning/2026/v3.xlsx"},
            {"name": "ASFmm - PLANNING SEMAINE 2026-05-02.xlsx", "path": "Planning/2026/v2.xlsx"},
        ],
    )

    out = find_planning_files_for_week(5, 2026)
    assert out == [
        "Planning/2026/v3.xlsx",
        "Planning/2026/v2.xlsx",
        "Planning/2026/v1.xlsx",
    ]


def test_load_planning_preview_graph_invalid_path(monkeypatch, tmp_path):
    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: True)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_tmp_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "asf_app.services.planning_exports_service.safe_cache_path",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad path")),
    )

    df, msg, path = load_planning_preview_with_path(5, 2026, "remote/../../danger.xlsx")
    assert df is None
    assert path is None
    assert "Chemin OneDrive invalide" in msg


def test_load_planning_preview_local_falls_back_to_pattern_candidate(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base = root / "Planning MAB" / "ASFmm PLANNING 2026"
    base.mkdir(parents=True, exist_ok=True)
    candidate = base / "Custom PLANNING 05 2026.xlsx"
    with pd.ExcelWriter(candidate) as writer:
        pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="Planning S05", index=False)

    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: False)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_onedrive_root", lambda: root)

    df_out, msg, used_path = load_planning_preview_with_path(5, 2026, None)
    assert used_path == candidate
    assert df_out is not None and not df_out.empty
    assert "utilisation de" in msg


def test_load_planning_preview_local_reports_missing_expected_sheets(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base = root / "Planning MAB" / "ASFmm PLANNING 2026"
    base.mkdir(parents=True, exist_ok=True)
    exact = base / "ASFmm - PLANNING SEMAINE 2026-05-01.xlsx"
    with pd.ExcelWriter(exact) as writer:
        pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="Other", index=False)

    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: False)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_onedrive_root", lambda: root)

    df_out, msg, used_path = load_planning_preview_with_path(5, 2026, None)
    assert df_out is None
    assert used_path == exact
    assert "Impossible de lire les feuilles" in msg


def test_load_planning_preview_graph_downloads_cache_file(monkeypatch, tmp_path):
    local_cache = tmp_path / "cache.xlsx"

    def _fake_download(_remote: str, local_path: Path, **_kwargs):
        with pd.ExcelWriter(local_path) as writer:
            pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="Export planning", index=False)
        return True

    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: True)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_tmp_dir", lambda: tmp_path)
    monkeypatch.setattr("asf_app.services.planning_exports_service.find_planning_files_for_week", lambda *_a, **_k: ["remote/planning.xlsx"])
    monkeypatch.setattr("asf_app.services.planning_exports_service.safe_cache_path", lambda *_a, **_k: local_cache)
    monkeypatch.setattr(cp, "download_onedrive_file", _fake_download)

    df_out, msg, used_path = load_planning_preview_with_path(5, 2026, None)
    assert used_path == local_cache
    assert df_out is not None and not df_out.empty
    assert "Export planning" in msg


def test_available_weeks_from_exports_local_parses_old_pattern(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base_dir = root / "Planning MAB" / "ASFmm PLANNING 2026"
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "ASFmm - PLANNING SEMAINE N° 08 - 2026 v2.xlsx").touch()

    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: False)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_onedrive_root", lambda: root)

    weeks = available_weeks_from_exports()
    assert (8, 2026) in weeks


def test_load_planning_preview_wrapper_delegates(monkeypatch, tmp_path):
    sentinel_df = pd.DataFrame({"A": [1]})
    sentinel_path = tmp_path / "x.xlsx"
    monkeypatch.setattr(
        "asf_app.services.planning_exports_service.load_planning_preview_with_path",
        lambda week, year, path_override: (sentinel_df, f"{week}-{year}-{path_override}", sentinel_path),
    )
    out_df, msg, used = load_planning_preview(4, 2026)
    assert out_df is sentinel_df
    assert msg == "4-2026-None"
    assert used == sentinel_path


def test_load_planning_preview_graph_returns_missing_when_no_candidates(monkeypatch, tmp_path):
    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: True)
    monkeypatch.setattr("asf_app.services.planning_exports_service.find_planning_files_for_week", lambda *_a, **_k: [])
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_tmp_dir", lambda: tmp_path)

    out_df, msg, used = load_planning_preview_with_path(9, 2026, None)
    assert out_df is None
    assert used is None
    assert "S09-2026" in msg


def test_load_planning_preview_graph_returns_missing_when_download_does_not_create_file(monkeypatch, tmp_path):
    cache_path = tmp_path / "cache.xlsx"
    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: True)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_tmp_dir", lambda: tmp_path)
    monkeypatch.setattr("asf_app.services.planning_exports_service.safe_cache_path", lambda *_a, **_k: cache_path)
    monkeypatch.setattr(cp, "download_onedrive_file", lambda *_a, **_k: False)

    out_df, msg, used = load_planning_preview_with_path(9, 2026, "remote/planning.xlsx")
    assert out_df is None
    assert used is None
    assert "remote/planning.xlsx" in msg


def test_load_planning_preview_local_returns_missing_when_no_match(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    (root / "Planning MAB" / "ASFmm PLANNING 2026").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: False)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_onedrive_root", lambda: root)

    out_df, msg, used = load_planning_preview_with_path(11, 2026, None)
    assert out_df is None
    assert used is None
    assert "Fichier introuvable" in msg


def test_load_planning_preview_local_pattern_match_with_missing_sheets_reports_combined_message(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base = root / "Planning MAB" / "ASFmm PLANNING 2026"
    base.mkdir(parents=True, exist_ok=True)
    candidate = base / "Custom PLANNING 05 2026.xlsx"
    with pd.ExcelWriter(candidate) as writer:
        pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="Other", index=False)

    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: False)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_onedrive_root", lambda: root)

    out_df, msg, used = load_planning_preview_with_path(5, 2026, None)
    assert out_df is None
    assert used == candidate
    assert "utilisation de" in msg
    assert "Impossible de lire les feuilles" in msg


def test_available_weeks_from_exports_graph_ignores_unparsable_week(monkeypatch):
    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: True)
    monkeypatch.setattr(
        cp,
        "list_onedrive_files",
        lambda *args, **kwargs: [{"name": "ASFmm - PLANNING SEMAINE 2026-XX-01.xlsx"}],
    )
    weeks = available_weeks_from_exports()
    # Le parser récupère "01" comme semaine via le motif permissif.
    assert weeks == {(1, 2026)}


def test_available_weeks_from_exports_local_missing_base_dir_returns_empty(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: False)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_onedrive_root", lambda: root)
    assert available_weeks_from_exports() == set()


def test_available_weeks_from_exports_local_skips_invalid_subfolders_and_files(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base = root / "Planning MAB"
    base.mkdir(parents=True, exist_ok=True)
    (base / "README.txt").write_text("x", encoding="utf-8")
    bad_year = base / "ASFmm PLANNING XX"
    bad_year.mkdir()
    good_year = base / "ASFmm PLANNING 2026"
    good_year.mkdir()
    (good_year / "ASFmm - PLANNING SEMAINE N° XX - 2026.xlsx").touch()

    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: False)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_onedrive_root", lambda: root)
    assert available_weeks_from_exports() == set()


def test_find_planning_files_for_week_local_missing_dir_returns_empty(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: False)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_onedrive_root", lambda: root)
    assert find_planning_files_for_week(4, 2026) == []


def test_find_planning_files_for_week_local_handles_stat_errors(tmp_path, monkeypatch):
    root = tmp_path / "onedrive"
    base = root / "Planning MAB" / "ASFmm PLANNING 2026"
    base.mkdir(parents=True, exist_ok=True)
    f1 = base / "ASFmm - PLANNING SEMAINE 2026-04-01.xlsx"
    f2 = base / "ASFmm - PLANNING SEMAINE 2026-04-02.xlsx"
    f1.touch()
    f2.touch()
    monkeypatch.setattr("asf_app.services.planning_exports_service.is_graph_onedrive", lambda: False)
    monkeypatch.setattr("asf_app.services.planning_exports_service.get_onedrive_root", lambda: root)
    monkeypatch.setattr(Path, "is_file", lambda *_a, **_k: True, raising=False)

    orig_stat = Path.stat

    def _patched_stat(path_obj: Path, *args, **kwargs):
        if path_obj.name.endswith("-02.xlsx"):
            raise OSError("boom")
        return orig_stat(path_obj, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _patched_stat, raising=False)
    out = find_planning_files_for_week(4, 2026)
    assert len(out) == 2


def test_load_planning_xlsx_returns_empty_for_missing_or_invalid_file(tmp_path, monkeypatch):
    missing = tmp_path / "missing.xlsx"
    assert load_planning_xlsx(missing).empty

    path = tmp_path / "broken.xlsx"
    path.write_text("not-an-excel", encoding="utf-8")
    monkeypatch.setattr(
        "asf_app.services.planning_exports_service.pd.read_excel",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad")),
    )
    assert load_planning_xlsx(path).empty


def test_load_planning_xlsx_returns_empty_for_empty_or_non_numeric_be(tmp_path, monkeypatch):
    path = tmp_path / "planning.xlsx"
    monkeypatch.setattr("asf_app.services.planning_exports_service.pd.read_excel", lambda *_a, **_k: pd.DataFrame())
    assert load_planning_xlsx(path).empty

    df_raw = pd.DataFrame(
        [
            ["", "", "Lundi 01/01", "Jean", "", "BRAZZAVILLE", "BZV", "CDG-BZV", "AF123", "10:00", "ABC", 2, "MM", "", "", "ASF", "HOP"],
        ]
    )
    monkeypatch.setattr("asf_app.services.planning_exports_service.pd.read_excel", lambda *_a, **_k: df_raw)
    assert load_planning_xlsx(path, default_year=2026).empty


def test_load_planning_xlsx_sets_nb_colis_to_zero_when_numeric_cast_fails(tmp_path, monkeypatch):
    path = tmp_path / "planning.xlsx"
    path.write_text("x", encoding="utf-8")
    df_raw = pd.DataFrame(
        [
            ["", "", "Lundi 01/01", "Jean", "", "BRAZZAVILLE", "BZV", "CDG-BZV", "AF123", "10:00", "250001", 2, "MM", "", "", "ASF", "HOP"],
        ]
    )
    monkeypatch.setattr("asf_app.services.planning_exports_service.pd.read_excel", lambda *_a, **_k: df_raw)
    monkeypatch.setattr(
        "asf_app.services.planning_exports_service.pd.to_numeric",
        lambda *_a, **_k: (_ for _ in ()).throw(TypeError("boom")),
    )
    out = load_planning_xlsx(path, default_year=2026)
    assert int(out.iloc[0]["nb_colis"]) == 0
