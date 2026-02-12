# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from utils.datetime_utils import (
    coerce_datetime,
    format_date_series,
    format_date_value,
    format_date_long_fr,
    format_time_value,
    parse_date_series,
    parse_time_series,
)
from utils.identifiers import format_vol_display, normalize_be_number
from utils.ui_helpers import format_be_label


def _norm_be(val: object) -> str:
    return normalize_be_number(val)


def _fmt_date_long(val: object) -> str:
    if val is None or str(val).strip() == "":
        return ""
    return format_date_long_fr(val, default=None)


def _fmt_time(val: object) -> str:
    out = format_time_value(val, allow_general_fallback=True, default=None)
    return out if out not in (None, "") else str(val)


def _fmt_vol(val: object) -> str:
    return format_vol_display(val) or str(val)


def _wrap_body(lines: list[str]) -> str:
    body = "<br>".join([str(l) for l in lines if l is not None])
    return f"<div style='font-family: Aptos, Segoe UI, sans-serif; font-size: 12pt;'>{body}</div>"


def _build_action_sentence(
    be_num: str,
    dest_iata: str,
    date_initial: str,
    action: str,
    new_date: str,
    vol_disp: str,
    bene_short: str,
) -> str:
    prefix = f"Le BE {be_num}, destination {dest_iata}, initialement prévu le {date_initial}"
    if action == "Annulation":
        return f"{prefix} sera annulé."
    if action == "Ajouter au planning":
        return f"Le BE {be_num}, destination {dest_iata}, sera ajouté le {new_date} sur le vol {vol_disp} avec {bene_short}."
    return f"{prefix} sera reprogrammé le {new_date} sur le vol {vol_disp} avec {bene_short}."


def _build_default_vol_tuple(
    *,
    prefill_date_new: object | None,
    prefill_vol_new: object | None,
    prefill_heure_new: object | None,
    be_scope: str,
    date_initial: object,
    current_vol: object,
    current_heure: object,
) -> tuple[str, str, str]:
    if prefill_date_new or prefill_vol_new or prefill_heure_new:
        return (
            str(prefill_date_new or ""),
            str(prefill_vol_new or ""),
            str(prefill_heure_new or ""),
        )
    if be_scope == "A planifier":
        return ("", "", "")
    return (str(date_initial), str(current_vol), str(current_heure))


def _build_vol_selection_data(
    vol_options: list[tuple[str, tuple[str, str, str]]],
    default_vol_tuple: tuple[str, str, str],
) -> tuple[list[str], list[tuple[str, str, str]], int]:
    vol_labels = [v[0] for v in vol_options] or ["Aucun vol disponible"]
    vol_values = [v[1] for v in vol_options] or [("", "", "")]
    default_idx = vol_values.index(default_vol_tuple) if default_vol_tuple in vol_values else 0
    return vol_labels, vol_values, default_idx


def _resolve_selected_vol(
    vol_labels: list[str],
    vol_values: list[tuple[str, str, str]],
    vol_choice: str,
) -> tuple[str, str, str]:
    if not vol_labels or not vol_values:
        return ("", "", "")
    idx = vol_labels.index(vol_choice) if vol_choice in vol_labels else 0
    return vol_values[idx]


def _build_bene_options(
    df_parambenev: pd.DataFrame | None,
    *,
    be_scope: str,
    status_for: Callable[[str], str],
) -> list[str]:
    bene_options: list[str] = []
    if df_parambenev is None or df_parambenev.empty:
        return bene_options
    for name in sorted(df_parambenev["Benevole"].dropna().unique()):
        if be_scope == "A planifier":
            bene_options.append(f"{name}")
        else:
            bene_options.append(f"{name} ({status_for(name)})")
    return bene_options


def _build_default_bene_label(
    *,
    prefill_bene: object | None,
    current_bene: object | None,
    be_scope: str,
    status_for: Callable[[str], str],
) -> str | None:
    if prefill_bene:
        prefill = str(prefill_bene)
        if be_scope == "A planifier":
            return prefill
        return f"{prefill} ({status_for(prefill)})"
    if current_bene:
        current = str(current_bene)
        if be_scope == "A planifier":
            return current
        return f"{current} ({status_for(current)})"
    return None


def _extract_bene_choice(bene_choice_label: str, bene_options: list[str]) -> str:
    return bene_choice_label.split(" (")[0] if bene_options else ""


def _fill_bene_name_from_parambenev(
    df_parambenev: pd.DataFrame | None,
    *,
    bene_choice: str,
    bene_prenom_court: str,
    bene_nom: str,
) -> tuple[str, str]:
    if not bene_choice or (bene_prenom_court and bene_nom):
        return bene_prenom_court, bene_nom
    try:
        if df_parambenev is None or df_parambenev.empty:
            return bene_prenom_court, bene_nom
        row_b = df_parambenev[df_parambenev["Benevole"] == bene_choice]
        if row_b.empty:
            return bene_prenom_court, bene_nom
        prenom_court = row_b.get("Prenom_Court", pd.Series([""])).iloc[0]
        nom = row_b.get("Nom", pd.Series([""])).iloc[0]
        return str(prenom_court or ""), str(nom or "")
    except Exception:
        return bene_prenom_court, bene_nom


def _split_emails(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(str(item).replace(",", ";").split(";"))
    else:
        parts = str(value).replace(",", ";").split(";")
    return [p.strip() for p in parts if p and str(p).strip()]


def _merge_emails(*values: object) -> list[str]:
    items: list[str] = []
    for value in values:
        items.extend(_split_emails(value))
    seen: set[str] = set()
    unique: list[str] = []
    for addr in items:
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(addr)
    return unique


def _dedupe_queue_by_be(queue: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    ignored: list[str] = []
    for upd in reversed(queue):
        key = _norm_be(upd.get("be_num", ""))
        if key in seen:
            ignored.append(str(upd.get("be_num", "")))
            continue
        seen.add(key)
        deduped.append(upd)
    deduped.reverse()
    return deduped, ignored


def _add_queue_item(
    queue: list[dict[str, Any]],
    queue_item: dict[str, Any],
    *,
    preview_path: Path | str | None,
    existing_queue_path: Path | str | None,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    if not preview_path:
        return None, "Impossible de trouver le fichier planning à mettre à jour."
    preview = Path(preview_path)
    if not preview.exists():
        return None, "Impossible de trouver le fichier planning à mettre à jour."
    if existing_queue_path and str(existing_queue_path) != str(preview):
        return None, "La liste d’attente contient un autre planning. Videz la liste avant d’ajouter."
    updated = list(queue)
    updated.append(queue_item)
    return updated, None


def _clear_queue_state(session_state: dict[str, Any], *, clear_payloads: bool) -> None:
    session_state["ship_update_queue"] = []
    session_state.pop("ship_update_queue_planning_path", None)
    session_state.pop("ship_update_queue_week", None)
    session_state.pop("ship_update_queue_year", None)
    if clear_payloads:
        session_state.pop("ship_update_payloads", None)


def _build_queue_dataframe(queue: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "BE": q.get("be_num"),
                "Action": q.get("action"),
                "Destination": q.get("dest_iata"),
                "Date": q.get("date_new_long"),
                "Vol": q.get("vol_display"),
                "Bénévole": q.get("bene_short"),
            }
            for q in queue
        ]
    )


def _build_queue_labels(queue: list[dict[str, Any]]) -> list[str]:
    return [
        f"{i + 1}. {q.get('dest_iata')} - BE {q.get('be_num')} - {q.get('action')} - {q.get('date_new_long')}"
        for i, q in enumerate(queue)
    ]


def _pop_prefill_values(session_state: dict[str, Any]) -> dict[str, Any]:
    prefill_item = session_state.pop("ship_update_prefill", None)
    if not isinstance(prefill_item, dict):
        prefill_item = {}
    return {
        "action": prefill_item.get("action"),
        "be_key": prefill_item.get("be_key"),
        "be_num": prefill_item.get("be_num"),
        "date_new": prefill_item.get("date_new"),
        "vol_new": prefill_item.get("vol_new"),
        "heure_new": prefill_item.get("heure_new"),
        "bene_choice": prefill_item.get("bene_choice"),
        "be_scope": prefill_item.get("be_scope"),
    }


def _build_queue_item(
    *,
    week: int,
    year: int,
    dest_iata: str,
    dest_label: object,
    selected_be: object,
    be_scope: str,
    date_initial_long: str,
    date_new_long: str,
    vol_disp: str,
    bene_short: str,
    expediteur_name: str,
    action_choice: str,
    action_sentence: str,
    be_source: str,
    preview_path: Path | str | None,
    be_row: pd.Series,
    date_new: object,
    vol_new: object,
    heure_new: object,
    bene_choice: object,
    current_bene: object,
    plan_row_full: pd.Series | None,
    bene_meta: dict[str, Any] | None,
    bene_changed: bool,
) -> dict[str, Any]:
    return {
        "week": week,
        "year": year,
        "dest_iata": dest_iata,
        "dest_label": dest_label,
        "be_num": str(selected_be),
        "be_key": str(selected_be),
        "be_scope": be_scope,
        "date_initial_long": date_initial_long,
        "date_new_long": date_new_long or date_initial_long,
        "vol_display": vol_disp,
        "bene_short": bene_short,
        "expediteur": expediteur_name,
        "action": action_choice,
        "action_sentence": action_sentence,
        "source": be_source,
        "planning_path": str(preview_path) if preview_path else "",
        "be_info": be_row.to_dict(),
        "date_new": date_new,
        "vol_new": vol_new,
        "heure_new": heure_new,
        "bene_choice": bene_choice or current_bene,
        "current_bene": current_bene,
        "plan_row_full": plan_row_full.to_dict() if plan_row_full is not None else {},
        "bene_meta": bene_meta if bene_meta is not None else {},
        "bene_changed": bene_changed,
    }


def _queue_to_batch_updates(deduped: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "action": u.get("action"),
            "be_num": u.get("be_num"),
            "dest_iata": u.get("dest_iata"),
            "date_new": u.get("date_new"),
            "vol_new": u.get("vol_new"),
            "heure_new": u.get("heure_new"),
            "bene_choice": u.get("bene_choice"),
            "be_info": u.get("be_info", {}),
            "plan_row_full": u.get("plan_row_full", {}),
            "bene_meta": u.get("bene_meta", {}),
            "bene_changed": u.get("bene_changed", False),
        }
        for u in deduped
    ]


def _prepare_queue_apply(
    queue: list[dict[str, Any]],
    *,
    queue_path: Path | str | None,
    preview_path: Path | str | None,
) -> tuple[Path | None, list[dict[str, Any]], list[str], str | None]:
    resolved_path = queue_path or preview_path
    if not resolved_path or not Path(resolved_path).exists():
        return None, [], [], "Impossible de trouver le fichier planning à mettre à jour."
    deduped, ignored = _dedupe_queue_by_be(queue)
    return Path(resolved_path), deduped, ignored, None


def _build_duplicate_be_warning(ignored: list[str]) -> str | None:
    if not ignored:
        return None
    return (
        "Plusieurs modifications sur le même BE détectées : "
        + ", ".join(sorted(set(str(i) for i in ignored)))
        + ". Les précédentes ont été ignorées."
    )


def _should_show_mag_central_cleanup_info(
    *,
    write_mag_central: bool,
    deduped: list[dict[str, Any]],
) -> bool:
    return bool(write_mag_central and any(u.get("action") == "Annulation" for u in deduped))


def _run_queue_apply_batch(
    *,
    queue_path: Path,
    deduped: list[dict[str, Any]],
    queue_week: object,
    queue_year: object,
    selected_week: int,
    selected_year: int,
    df_vols: pd.DataFrame | None,
    df_parambenev: pd.DataFrame | None,
    df_dispos: pd.DataFrame | None,
    df_paramdest: pd.DataFrame | None,
    increment_q1: bool,
    write_mag_central: bool,
    tdb_source_path: Path | str | None,
    apply_updates_fn: Callable[..., Path | str | None],
    export_pdf_fn: Callable[[Path], Path | str],
) -> dict[str, Any]:
    updates = _queue_to_batch_updates(deduped)
    week = int(queue_week) if queue_week is not None else int(selected_week)
    year = int(queue_year) if queue_year is not None else int(selected_year)

    try:
        updated_raw = apply_updates_fn(
            Path(queue_path),
            updates,
            week=week,
            year=year,
            df_vols=df_vols,
            df_parambenev=df_parambenev,
            df_dispos=df_dispos,
            df_paramdest=df_paramdest,
            increment_version=increment_q1,
            write_mag_central=write_mag_central,
            tdb_source_path=tdb_source_path,
        )
        updated_path = Path(updated_raw) if updated_raw else Path(queue_path)
    except Exception as exc:
        return {
            "error": f"Erreur lors de la mise à jour du planning : {exc}",
            "updated_path": None,
            "pdf_path": None,
            "pdf_error": None,
            "payloads": [],
            "week": week,
            "year": year,
        }

    pdf_path: Path | None = None
    pdf_error: str | None = None
    try:
        generated = export_pdf_fn(updated_path)
        pdf_path = Path(generated) if generated else None
    except Exception as exc_pdf:
        pdf_path = None
        pdf_error = str(exc_pdf)

    payloads = _build_notification_payloads(
        deduped,
        updated_path=updated_path,
        pdf_path=pdf_path,
        week=week,
        year=year,
    )
    return {
        "error": None,
        "updated_path": updated_path,
        "pdf_path": pdf_path,
        "pdf_error": pdf_error,
        "payloads": payloads,
        "week": week,
        "year": year,
    }


def _build_notification_payloads(
    deduped: list[dict[str, Any]],
    *,
    updated_path: Path | str,
    pdf_path: Path | str | None,
    week: int,
    year: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for u in deduped:
        item = dict(u)
        item["planning_path"] = str(updated_path)
        item["planning_pdf_path"] = str(pdf_path) if pdf_path else ""
        item["week"] = int(week)
        item["year"] = int(year)
        out.append(item)
    return out


def _build_body_lines_multi(items: list[dict[str, Any]], *, week: int, year: int) -> list[str]:
    lines = [
        "Bonjour,",
        "",
        f"Mise à jour du planning S{week:02d} - {year} :",
        "",
    ]
    for item in items:
        lines.append(str(item.get("action_sentence", "")))
        lines.append("")
    lines.append("Cordialement,")
    return lines


def _notification_period_from_payloads(
    payloads: list[dict[str, Any]],
    *,
    default_week: int,
    default_year: int,
) -> tuple[int, int]:
    week = int(default_week)
    year = int(default_year)
    if not payloads:
        return week, year
    first = payloads[0] if isinstance(payloads[0], dict) else {}
    try:
        week = int(first.get("week", week))
    except Exception:
        week = int(default_week)
    try:
        year = int(first.get("year", year))
    except Exception:
        year = int(default_year)
    return week, year


def _collect_benevole_emails(payloads: list[dict[str, Any]], df_parambenev: pd.DataFrame | None) -> list[str]:
    def _bene_email(name: object) -> str:
        if not name or df_parambenev is None or getattr(df_parambenev, "empty", True):
            return ""
        row = df_parambenev[df_parambenev["Benevole"] == name]
        if row.empty:
            return ""
        return str(row.get("Email", pd.Series([""])).iloc[0]).strip()

    bene_emails: list[str] = []
    for item in payloads:
        action = item.get("action", "")
        if action == "Changement de date ou bénévole":
            for ben in {item.get("current_bene"), item.get("bene_choice")}:
                mail = _bene_email(ben)
                if mail:
                    bene_emails.append(mail)
        else:
            mail = _bene_email(item.get("bene_choice") or item.get("current_bene"))
            if mail:
                bene_emails.append(mail)
    return bene_emails


def _resolve_planning_version_major(
    planning_path: str | Path | None,
    *,
    parse_version_from_name: Callable[[Path], tuple[int, int]],
) -> int:
    if not planning_path:
        return 1
    try:
        major, _ = parse_version_from_name(Path(planning_path))
        return int(major)
    except Exception:
        return 1


def _resolve_notification_pdf_path(
    planning_path: str | Path | None,
    payload_pdf_path: str | Path | None,
    *,
    export_pdf_fn: Callable[[Path], Path | str] | None = None,
) -> str:
    pdf_path = str(payload_pdf_path or "")
    if pdf_path and not Path(pdf_path).exists():
        pdf_path = ""

    planning = str(planning_path or "")
    if not pdf_path and planning:
        candidate = Path(planning).with_suffix(".pdf")
        if candidate.exists():
            pdf_path = str(candidate)

    if not pdf_path and planning and export_pdf_fn is not None:
        try:
            pdf_path = str(export_pdf_fn(Path(planning)))
        except Exception:
            pdf_path = ""
    return pdf_path


def _build_asf_notification_draft(
    payloads: list[dict[str, Any]],
    bene_emails: list[str],
    *,
    default_week: int,
    default_year: int,
    parse_version_from_name: Callable[[Path], tuple[int, int]],
    export_pdf_fn: Callable[[Path], Path | str] | None = None,
) -> dict[str, Any]:
    week, year = _notification_period_from_payloads(
        payloads,
        default_week=default_week,
        default_year=default_year,
    )
    planning_path = ""
    payload_pdf_path = ""
    if payloads:
        first = payloads[0] if isinstance(payloads[0], dict) else {}
        planning_path = str(first.get("planning_path", "") or "")
        payload_pdf_path = str(first.get("planning_pdf_path", "") or "")

    version_major = _resolve_planning_version_major(
        planning_path,
        parse_version_from_name=parse_version_from_name,
    )
    pdf_path = _resolve_notification_pdf_path(
        planning_path,
        payload_pdf_path,
        export_pdf_fn=export_pdf_fn,
    )
    to_list = _merge_emails(
        ["messmed@aviation-sans-frontieres-fr.org", *[m for m in bene_emails if m]]
    )
    return {
        "week": week,
        "year": year,
        "to_list": to_list,
        "cc_list": None,
        "subject": f"MAJ Planning S{week:02d}-{int(version_major):02d}",
        "body_html": _wrap_body(_build_body_lines_multi(payloads, week=week, year=year)),
        "attachments": [pdf_path] if pdf_path else None,
    }


def _build_destination_notification_drafts(
    payloads: list[dict[str, Any]],
    df_paramdest: pd.DataFrame | None,
    *,
    week: int,
    year: int,
    get_emails_for_destination: Callable[[pd.DataFrame | None, str], tuple[object, object]],
) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    dest_groups = _group_payloads_by_destination(payloads)
    for dest_key, items in dest_groups.items():
        to_dest, cc_dest = get_emails_for_destination(df_paramdest, dest_key)
        if not to_dest:
            to_dest, cc_dest = get_emails_for_destination(df_paramdest, dest_key)
        to_dest_list = _merge_emails(to_dest)
        cc_dest_list = _merge_emails(cc_dest, "messmed@aviation-sans-frontieres-fr.org")
        if not to_dest_list:
            continue
        drafts.append(
            {
                "name": dest_key,
                "to_list": to_dest_list,
                "cc_list": cc_dest_list,
                "subject": f"MAJ Planning S{week:02d} - {dest_key}",
                "body_html": _wrap_body(_build_body_lines_multi(items, week=week, year=year)),
                "attachments": None,
            }
        )
    return drafts


def _build_expediteur_notification_drafts(
    payloads: list[dict[str, Any]],
    df_paramexpediteur: pd.DataFrame | None,
    *,
    week: int,
    year: int,
    get_emails_for_expediteur: Callable[[pd.DataFrame | None, str], tuple[object, object]],
) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    exp_groups = _group_payloads_by_expediteur(payloads)
    for exp_name, items in exp_groups.items():
        to_exp, cc_exp = get_emails_for_expediteur(df_paramexpediteur, exp_name)
        to_exp_list = _merge_emails(to_exp)
        cc_exp_list = _merge_emails(cc_exp, "messmed@aviation-sans-frontieres-fr.org")
        if not to_exp_list:
            continue
        drafts.append(
            {
                "name": exp_name,
                "to_list": to_exp_list,
                "cc_list": cc_exp_list,
                "subject": f"{exp_name} - MAJ Planning S{week:02d}",
                "body_html": _wrap_body(_build_body_lines_multi(items, week=week, year=year)),
                "attachments": None,
            }
        )
    return drafts


def _group_payloads_by_destination(payloads: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in payloads:
        dest_key = str(item.get("dest_iata") or item.get("dest_label") or "").upper()
        if not dest_key:
            continue
        groups.setdefault(dest_key, []).append(item)
    return groups


def _group_payloads_by_expediteur(payloads: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in payloads:
        exp_name = str(item.get("expediteur", "") or "").strip()
        if not exp_name or exp_name.upper() == "ASF":
            continue
        groups.setdefault(exp_name, []).append(item)
    return groups


def _normalize_be_key_for_select(val: object, *, year: object | None = None) -> str:
    """Normalise un BE pour l'affichage/sélection (préserve YY + 4 chiffres si valeur YYYYxxxx).
    Si le BE est au format 00xxxx et qu'une année est connue, préfixe avec YY.
    """
    digits = re.sub(r"\D+", "", str(val or "").strip())
    if not digits:
        return ""
    if len(digits) >= 8 and digits.startswith("20"):
        return f"{digits[2:4]}{digits[-4:]}"
    year_val = ""
    try:
        if year is not None and not pd.isna(year) and str(year).strip() not in ("", "NaT"):
            year_val = str(int(year))[-2:]
    except Exception:
        year_val = ""
    if len(digits) >= 6:
        if digits.startswith("00") and year_val:
            return f"{year_val}{digits[-4:]}"
        return digits[-6:]
    if year_val:
        return f"{year_val}{digits.zfill(4)}"
    return digits.zfill(6)


def _dest_to_iata(dest_raw: str, df_paramdest: pd.DataFrame) -> str:
    dest = str(dest_raw).strip().upper()
    if len(dest) == 3:
        return dest
    try:
        mapping = (
            df_paramdest.dropna(subset=["Dest_Ville", "Dest_IATA"])
            .assign(Dest_Ville_UP=lambda d: d["Dest_Ville"].astype(str).str.upper().str.strip())
            .drop_duplicates(subset=["Dest_Ville_UP"])
            .set_index("Dest_Ville_UP")["Dest_IATA"]
            .astype(str)
            .str.upper()
            .to_dict()
        )
        return mapping.get(dest, dest)
    except Exception:
        return dest


def _build_planif_be_options(
    df_be_planif: pd.DataFrame,
    planned_set: set[str],
) -> list[tuple[str, str, str, pd.Series]]:
    if df_be_planif is None or df_be_planif.empty:
        return []

    options: list[tuple[str, str, str, pd.Series]] = []
    for _, r in df_be_planif.iterrows():
        dest = str(r.get("Destination", "")).upper()
        be_num = str(r.get("BE_Numero", ""))
        nb_colis = r.get("BE_Nb_Colis", r.get("BE_Nb_Colis_MAG", ""))
        nb_colis = int(nb_colis) if pd.notna(nb_colis) else ""
        type_colis = str(r.get("BE_Type", "")).upper()
        status = "déjà au planning" if be_num in planned_set else "non planifié"
        date_str = str(r.get("Date_Vol", r.get("BE_Date_Vol", "")) or "")
        label = format_be_label(dest, be_num, nb_colis, type_colis, status, date_str)
        options.append((dest, be_num, label, r))
    return sorted(options, key=lambda x: (x[0], x[1]))


def _prepare_be_lookup(
    df_be_plan: pd.DataFrame | None,
    df_be_d: pd.DataFrame | None,
    df_paramdest: pd.DataFrame,
) -> tuple[pd.DataFrame, str | None]:
    df_be_all = pd.DataFrame()
    if df_be_plan is not None and not df_be_plan.empty:
        df_be_all = pd.concat([df_be_all, df_be_plan], ignore_index=True)
    if df_be_d is not None and not df_be_d.empty:
        df_be_all = pd.concat([df_be_all, df_be_d], ignore_index=True)
    if df_be_all.empty:
        return pd.DataFrame(), "empty"

    df_be_all["BE_Numero_Str"] = df_be_all["BE_Numero_Str"].fillna("").astype(str)
    df_be_all = df_be_all[df_be_all["BE_Numero_Str"].str.strip() != ""]
    if df_be_all.empty:
        return pd.DataFrame(), "missing_be"

    df_be_all["Dest_IATA_Label"] = df_be_all.get("Destination", "").apply(
        lambda val: _dest_to_iata(val, df_paramdest)
    )
    df_be_all["BE_Key"] = df_be_all.apply(
        lambda r: _normalize_be_key_for_select(r.get("BE_Numero_Str", ""), year=r.get("Year")),
        axis=1,
    )
    df_be_all = df_be_all[df_be_all["BE_Key"] != ""]
    df_be_all["BE_Num_Display"] = df_be_all["BE_Key"]
    source_series = (
        df_be_all["Source"] if "Source" in df_be_all.columns else pd.Series("", index=df_be_all.index)
    )
    df_be_all["Source_rank"] = source_series.astype(str).str.lower().eq("planning").astype(int)
    if "_STATUS" in df_be_all.columns:
        df_be_all["_STATUS"] = df_be_all["_STATUS"].fillna("normal").astype(str).str.lower()
    else:
        df_be_all["_STATUS"] = "normal"

    def _status_rank(val: str) -> int:
        sval = str(val or "").strip().lower()
        if sval.startswith("new"):
            return 3
        if sval.startswith("old"):
            return 0
        if sval.startswith("orig"):
            return 2
        if sval in ("normal", ""):
            return 2
        return 1

    df_be_all["Status_rank"] = df_be_all["_STATUS"].apply(_status_rank)
    date_series = (
        df_be_all["Date_Vol"] if "Date_Vol" in df_be_all.columns else pd.Series(pd.NaT, index=df_be_all.index)
    )
    df_be_all["_DATE_SORT"] = coerce_datetime(date_series, errors="coerce")
    df_be_all["_DATE_SORT"] = df_be_all["_DATE_SORT"].fillna(pd.Timestamp.min)
    df_be_all["Prefix_rank"] = (~df_be_all["BE_Key"].str.startswith("00")).astype(int)
    df_be_all["TAIL4"] = df_be_all["BE_Key"].str[-4:]
    has_non_zero_tail = df_be_all.groupby("TAIL4")["Prefix_rank"].transform(
        lambda s: (s == 1).any()
    )
    mask_drop = (df_be_all["BE_Key"].str.startswith("00")) & has_non_zero_tail
    df_be_all = df_be_all[~mask_drop]
    df_be_all = df_be_all.sort_values(
        by=["BE_Key", "Status_rank", "Source_rank", "_DATE_SORT"],
        ascending=[True, False, False, False],
        kind="mergesort",
    )
    df_be_all = df_be_all[~df_be_all["BE_Key"].duplicated(keep="first")]
    df_be_all = df_be_all.sort_values(
        by=["Dest_IATA_Label", "TAIL4", "Prefix_rank", "Source_rank", "BE_Key"],
        ascending=[True, True, False, False, True],
        kind="mergesort",
    )
    return df_be_all.set_index("BE_Key"), None


def _format_be_option_label(num_str: str, be_lookup: pd.DataFrame) -> str:
    if num_str in be_lookup.index:
        row = be_lookup.loc[num_str]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        dest = str(row.get("Dest_IATA_Label", row.get("Destination", "")) or "").upper()
        nb = pd.to_numeric(row.get("BE_Nb_Colis", 0), errors="coerce")
        nb_int = int(nb) if pd.notna(nb) else (row.get("BE_Nb_Colis", "") or "")
        be_type = str(row.get("BE_Type", "") or "").upper()
        date_disp = _fmt_date_long(row.get("Date_Vol", ""))
        date_part = date_disp if date_disp not in (None, "", "NaT") else "A planifier"
        be_disp = str(row.get("BE_Num_Display", num_str)).zfill(6)
        return f"{dest} - BE {be_disp} - {nb_int} colis - {be_type} - {date_part}"
    return str(num_str)


def _build_bene_meta(df_parambenev: pd.DataFrame | None, bene_choice: str) -> dict[str, Any]:
    bene_meta: dict[str, Any] = {}
    if df_parambenev is not None and not df_parambenev.empty and bene_choice:
        row_bm = df_parambenev[df_parambenev["Benevole"] == bene_choice]
        if not row_bm.empty:
            rb = row_bm.iloc[0]
            bene_meta = {
                "Benevole": bene_choice,
                "ID": rb.get("ID", ""),
                "Telephone": rb.get("Telephone", ""),
                "Benevole_Prenom": rb.get("Prenom", ""),
                "Benevole_Prenom_Court": rb.get("Prenom_Court", ""),
                "Benevole_Nom": rb.get("Nom", ""),
                "ID_UP": rb.get("ID", ""),
                "Benev_UP": bene_choice.upper(),
                "ID_BEN_ID": rb.get("ID", ""),
                "Benevole_BEN_ID": rb.get("Benevole", bene_choice),
                "Nom": rb.get("Nom", ""),
                "Prenom": rb.get("Prenom", ""),
                "Prenom_Court": rb.get("Prenom_Court", ""),
                "Max_Jours_Semaine": rb.get("Max_Jours_Semaine", ""),
                "Max_Exp_Semaine": rb.get("Max_Exp_Semaine", ""),
                "Max_Exp_Jour": rb.get("Max_Exp_Jour", ""),
                "Attente_Max_Heures": rb.get("Attente_Max_Heures", ""),
                "Telephone_BEN_ID": rb.get("Telephone", rb.get("Telephone_BEN_ID", "")),
                "Email": rb.get("Email", ""),
                "Benev_UP_BEN_ID": str(rb.get("Benevole", bene_choice)).upper(),
                "ID_BENEVOLE": rb.get("ID", ""),
            }
    return bene_meta


def _prepare_dispo(df_dispos: pd.DataFrame) -> pd.DataFrame:
    df = df_dispos.copy()
    df["Date"] = parse_date_series(df.get("Date"), allow_dayfirst_false=False).dt.date
    arr_parsed = parse_time_series(df.get("Heure_Arrivee", ""), allow_general_fallback=True)
    dep_parsed = parse_time_series(df.get("Heure_Depart", ""), allow_general_fallback=True)
    df["Arr"] = arr_parsed.dt.time
    df["Dep"] = dep_parsed.dt.time
    return df


def _coerce_display_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Force certains champs à être affichés comme texte (téléphones, etc.)
    pour éviter les erreurs Arrow lors de l'aperçu.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        col_l = str(col).lower()
        if "telephone" in col_l or "phone" in col_l:
            out[col] = out[col].astype(str)
    return out


def _weeks_from_status_df(df_status: pd.DataFrame | None) -> set[tuple[int, int]]:
    if df_status is None or df_status.empty:
        return set()
    required = {"Week", "Year"}
    if not required.issubset(set(df_status.columns)):
        return set()

    weeks_set: set[tuple[int, int]] = set()
    for week_val, year_val in df_status[["Week", "Year"]].dropna().itertuples(index=False, name=None):
        try:
            weeks_set.add((int(week_val), int(year_val)))
        except Exception:
            continue
    return weeks_set


def _build_week_selector_data(weeks_set: set[tuple[int, int]]) -> tuple[list[tuple[int, int]], list[str], dict[str, tuple[int, int]]]:
    weeks = sorted(weeks_set, key=lambda pair: (pair[1], pair[0]), reverse=True)
    labels = [f"{year} - Semaine {week:02d}" for week, year in weeks]
    week_map = {label: pair for label, pair in zip(labels, weeks)}
    return weeks, labels, week_map


def _build_planning_version_choices(
    planning_candidates: list[Path | str],
    *,
    parse_version_from_name: Callable[[Path], tuple[int, int]],
) -> tuple[list[str], dict[str, Path | str]]:
    labels: list[str] = []
    path_map: dict[str, Path | str] = {}
    for candidate in planning_candidates:
        candidate_path = Path(candidate) if isinstance(candidate, str) else candidate
        major, minor = parse_version_from_name(candidate_path)
        ver_label = f"v{major}" + (f"-{minor}" if minor else "")
        label = f"{ver_label} — {candidate_path.name}"
        labels.append(label)
        path_map[label] = candidate
    return labels, path_map


def _format_preview_dataframe(df_preview: pd.DataFrame) -> pd.DataFrame:
    out = _coerce_display_types(df_preview)
    for col in out.columns:
        if "Date" in col:
            out[col] = format_date_series(
                out[col],
                fmt="%d/%m/%y",
                allow_dayfirst_false=True,
            )
        if "Heure" in col:
            out[col] = out[col].apply(
                lambda value: format_time_value(value, fmt="%Hh%M", default=str(value))
            )

    def _fmt_cell(value: object) -> object:
        if isinstance(value, (dt.datetime, dt.date, pd.Timestamp)):
            return format_date_value(value, fmt="%d/%m/%y", default="")
        if isinstance(value, dt.time):
            return format_time_value(value, fmt="%Hh%M", default="")
        return value

    return out.apply(lambda col: col.map(_fmt_cell))


def _load_export_planning_sheet(preview_path: Path | str | None) -> pd.DataFrame | None:
    if not preview_path:
        return None
    path = Path(preview_path)
    if not path.exists():
        return None
    try:
        return pd.read_excel(path, sheet_name="Export planning")
    except Exception:
        return None


def _select_source_for_be(
    df_export_planning: pd.DataFrame | None,
    df_preview: pd.DataFrame | None,
) -> pd.DataFrame | None:
    if df_export_planning is not None and not df_export_planning.empty:
        return df_export_planning
    return df_preview


def _bene_status(
    df_dispo: pd.DataFrame,
    df_planning: pd.DataFrame,
    name: str,
    date_str: str,
    heure_str: str,
    vol_str: str | None = None,
) -> str:
    try:
        d = coerce_datetime(date_str).date()
        h = coerce_datetime(heure_str).time()
    except Exception:
        return "indisponible"

    rows = df_dispo[df_dispo["Benevole"] == name]
    rows_same_day = rows[rows["Date"] == d]
    already = False
    if df_planning is not None and not df_planning.empty:
        mask = (
            (df_planning.get("Benevole", pd.Series(dtype=str)).astype(str) == str(name))
            & (df_planning.get("Date_Vol", pd.Series(dtype=str)).astype(str) == str(date_str))
        )
        if vol_str is not None:
            mask = mask & (
                df_planning.get("Numero_Vol", pd.Series(dtype=str)).astype(str) == str(vol_str)
            )
        already = mask.any()

    if already:
        return "déjà affecté sur ce créneau"
    if rows_same_day.empty:
        return "indisponible"

    has_info = False
    ok_dispo = False
    for _, row in rows_same_day.iterrows():
        arr = row["Arr"]
        dep = row["Dep"]
        if arr is None and dep is None:
            continue
        has_info = True
        arr = arr or h
        dep = dep or h
        if arr <= h <= dep:
            ok_dispo = True
            break

    if not has_info:
        return "inconnu"
    return "disponible" if ok_dispo else "indisponible"


def _collect_be_from_planning(df_prev: pd.DataFrame, week: int, year: int) -> pd.DataFrame:
    """
    Extrait les BE présents dans le planning exporté sélectionné.
    """
    if df_prev is None or df_prev.empty:
        return pd.DataFrame()

    df = df_prev.copy()

    be_cols = [c for c in df.columns if "BE" in str(c).upper() and "NUM" in str(c).upper()]
    be_col = be_cols[0] if be_cols else None
    if be_col is None:
        return pd.DataFrame()

    df_out = pd.DataFrame()
    df_out["BE_Numero_Str"] = (
        df[be_col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    )

    dest_col = None
    for cand in ["Destination", "Dest_IATA", "Ville", "DESTINATION"]:
        if cand in df.columns:
            dest_col = cand
            break
    df_out["Destination"] = df.get(dest_col, "")

    date_col = None
    for cand in ["Date_Vol", "DATE", "Date", "Date Vol"]:
        if cand in df.columns:
            date_col = cand
            break
    df_out["Date_Vol"] = coerce_datetime(
        df.get(date_col, ""),
        errors="coerce",
        dayfirst=True,
        format="%d/%m/%y",
    )
    iso = df_out["Date_Vol"].dt.isocalendar()
    df_out["Week"] = iso.week.astype("Int64")
    df_out["Year"] = iso.year.astype("Int64")
    df_out = df_out[(df_out["Week"] == week) & (df_out["Year"] == year)]

    vol_col = None
    for cand in ["Vol", "Numero_Vol", "NUMERO VOL", "Numero Vol"]:
        if cand in df.columns:
            vol_col = cand
            break
    heure_col = None
    for cand in ["Heure_Vol", "Heure", "HEURE VOL", "HEURE"]:
        if cand in df.columns:
            heure_col = cand
            break
    df_out["Numero_Vol"] = df.get(vol_col, "")
    df_out["Heure_Vol"] = df.get(heure_col, "")

    coli_col = None
    for cand in ["BE_Nb_Colis", "Nb_Colis", "NB COLIS", "NB_COLIS"]:
        if cand in df.columns:
            coli_col = cand
            break
    type_col = None
    for cand in ["BE_Type", "Type", "TYPE"]:
        if cand in df.columns:
            type_col = cand
            break
    df_out["BE_Nb_Colis"] = df.get(coli_col, 0)
    df_out["BE_Type"] = df.get(type_col, "")
    if "_STATUS" in df.columns:
        df_out["_STATUS"] = df.get("_STATUS", "normal")
    else:
        df_out["_STATUS"] = "normal"
    df_out["Source"] = "planning"
    return df_out


def _find_row_in_df(df: pd.DataFrame, be_num: str) -> pd.Series | None:
    """Retourne la première ligne du df dont le numéro BE correspond."""
    if df is None or df.empty:
        return None
    df_tmp = df.copy()
    be_cols = [c for c in df_tmp.columns if "BE" in str(c).upper() and "NUM" in str(c).upper()]
    for col in be_cols:
        df_tmp["_BE_MATCH"] = (
            df_tmp[col].astype(str).str.replace(r"\\.0$", "", regex=True).str.strip()
        )
        match = df_tmp[df_tmp["_BE_MATCH"].str.endswith(str(be_num).strip())]
        if not match.empty:
            return match.iloc[0]
    return None
