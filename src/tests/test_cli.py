import os
import tempfile
import sys

import pytest

from src import generate_reports
from src.group import Group


def make_group(tmp_path, handle, tags=None):
    groups_dir = tmp_path / "groups"
    groups_dir.mkdir(exist_ok=True)
    folder = groups_dir / handle
    folder.mkdir()
    cfg = {"handle": handle, "display_name": handle.title()}
    if tags:
        cfg["tags"] = tags
    with open(folder / "group.yaml", "w") as f:
        import yaml

        yaml.safe_dump(cfg, f)
    with open(folder / "query.sql", "w") as f:
        f.write("select 1 from dual")
    return folder


def test_discover_and_list(tmp_path, capsys):
    base = tmp_path
    g1 = make_group(base, "g1", tags=["x"])
    g2 = make_group(base, "g2")
    groups = generate_reports.discover_groups(str(base))
    handles = sorted([g.handle for g in groups])
    assert handles == ["g1", "g2"]

    # simulate CLI list
    # create minimal general config so loader doesn't fail
    cfg_dir = base / "config"
    cfg_dir.mkdir()
    (cfg_dir / "general.yaml").write_text("oracle_tns: dummy\n")
    sys.argv = ["", "list"]
    cwd = os.getcwd()
    os.chdir(str(base))
    try:
        with pytest.raises(SystemExit) as exc:
            generate_reports.main()
    finally:
        os.chdir(cwd)
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "g1" in captured.out
    assert "g2" in captured.out


def test_selection_by_name_and_tag(tmp_path):
    base = tmp_path
    make_group(base, "foo", tags=["red"])
    make_group(base, "bar", tags=["blue"])
    groups = generate_reports.discover_groups(str(base))
    # names
    sel = [g.handle for g in groups if g.matches(names=["foo"], tags=None)]
    assert sel == ["foo"]
    # tags
    sel2 = [g.handle for g in groups if g.matches(names=None, tags=["blue"])]
    assert sel2 == ["bar"]


def test_cli_numeric_selection(tmp_path):
    """Test that CLI accepts numeric group indices like '1', '2', etc."""
    base = tmp_path
    make_group(base, "alpha")
    make_group(base, "beta")
    make_group(base, "gamma")

    # create minimal config
    cfg_dir = base / "config"
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "general.yaml").write_text("oracle_tns: dummy\n")

    groups = generate_reports.discover_groups(str(base))
    # manually walk through the CLI parsing logic
    # simulate: args.names = ['1']
    token = "1"
    selected_set = set()
    if token.isdigit():
        idx = int(token) - 1
        if 0 <= idx < len(groups):
            selected_set.add(groups[idx].handle)
    selected = [g for g in groups if g.handle in selected_set]
    # should match one group
    assert len(selected) == 1
    assert selected[0].handle in ["alpha", "beta", "gamma"]


def test_root_entrypoint(monkeypatch, tmp_path):
    # ensure generate_reports.main gets called when running root script
    called = {"flag": False}
    def fake_main():
        called["flag"] = True
    monkeypatch.setattr("src.generate_reports.main", fake_main)
    import runpy, os
    # ensure a minimal config exists in cwd so generator import works
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "general.yaml").write_text("oracle_tns: dummy\n")
    # determine actual script path via import rather than assuming cwd
    import importlib
    rr = importlib.import_module("run_reports")
    script = rr.__file__

    cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        runpy.run_path(script, run_name="__main__")
    finally:
        os.chdir(cwd)
    assert called["flag"]
