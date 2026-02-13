# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_tests_collected():
    mod = _load_module_from_path("quality_dashboard_parse", Path("tools/quality_dashboard.py"))
    assert mod._parse_tests_collected("475 tests collected in 1.00s") == 475
    assert mod._parse_tests_collected("no tests collected") is None


def test_read_coverage_and_low_modules(tmp_path):
    mod = _load_module_from_path("quality_dashboard_coverage", Path("tools/quality_dashboard.py"))
    coverage_xml = tmp_path / "coverage.xml"
    coverage_xml.write_text(
        """<?xml version="1.0" ?>
<coverage line-rate="0.7828">
  <packages>
    <package name="asf_app">
      <classes>
        <class name="good" filename="asf_app/good.py" line-rate="0.95" lines-valid="100"/>
        <class name="bad" filename="asf_app/bad.py" line-rate="0.40" lines-valid="200"/>
      </classes>
    </package>
  </packages>
</coverage>
""",
        encoding="utf-8",
    )
    assert mod._read_coverage_percent(coverage_xml) == 78.28
    low = mod._low_coverage_modules(coverage_xml, limit=2)
    assert low[0][0] == "asf_app/bad.py"
    assert low[0][1] == 40.0


def test_low_coverage_modules_fallbacks_to_lines_nodes_count(tmp_path):
    mod = _load_module_from_path("quality_dashboard_lines_count", Path("tools/quality_dashboard.py"))
    coverage_xml = tmp_path / "coverage.xml"
    coverage_xml.write_text(
        """<?xml version="1.0" ?>
<coverage line-rate="0.80">
  <packages>
    <package name="pkg">
      <classes>
        <class name="mod" filename="pkg/mod.py" line-rate="0.60">
          <lines>
            <line number="1" hits="1"/>
            <line number="2" hits="0"/>
            <line number="3" hits="1"/>
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
""",
        encoding="utf-8",
    )
    low = mod._low_coverage_modules(coverage_xml, limit=1)
    assert low[0][0] == "pkg/mod.py"
    assert low[0][2] == 3


def test_history_append_and_tail(tmp_path):
    mod = _load_module_from_path("quality_dashboard_history", Path("tools/quality_dashboard.py"))
    history_file = tmp_path / "quality_history.csv"
    snap = mod.QualitySnapshot(
        generated_at="2026-02-13 10:00:00 UTC",
        iso_week="2026-W07",
        branch="main",
        commit="abc1234",
        tests_collected=475,
        coverage_percent=78.28,
        coverage_target=75,
    )
    mod._append_history_row(history_file, snap)
    tail = mod._read_history_tail(history_file, limit=10)
    assert len(tail) == 1
    assert tail[0]["tests_collected"] == "475"
    assert tail[0]["coverage_target"] == "75"


def test_main_generates_dashboard_and_history(tmp_path, monkeypatch):
    mod = _load_module_from_path("quality_dashboard_main", Path("tools/quality_dashboard.py"))
    output = tmp_path / "QUALITY_DASHBOARD.md"
    history = tmp_path / "QUALITY_DASHBOARD_HISTORY.csv"

    monkeypatch.setattr(mod, "_collect_tests_collected", lambda _py: 480)
    monkeypatch.setattr(mod, "_read_coverage_percent", lambda _p: 79.5)
    monkeypatch.setattr(mod, "_read_default_coverage_target", lambda: 75)
    monkeypatch.setattr(mod, "_low_coverage_modules", lambda _p: [("asf_app/low.py", 51.0, 40)])
    monkeypatch.setattr(mod, "_resolve_python", lambda: "python3")
    monkeypatch.setattr(mod, "_git_value", lambda _args, default: default)
    monkeypatch.setattr(
        mod.sys,
        "argv",
        [
            "quality_dashboard.py",
            "--output",
            str(output),
            "--history",
            str(history),
        ],
    )

    assert mod.main() == 0
    assert output.exists()
    assert history.exists()
    content = output.read_text(encoding="utf-8")
    assert "Current Snapshot" in content
    assert "480" in content
    assert "79.5" in content
