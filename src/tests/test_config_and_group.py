import os
import tempfile
import yaml

from src.config import load_general_config, load_group_config
from src.group import Group
from src.services.group_service import GroupService


def test_general_config_defaults(tmp_path):
    cfg_file = tmp_path / "general.yaml"
    cfg_file.write_text("oracle_tns: test_tns\n")
    cfg = load_general_config(str(cfg_file))
    assert cfg["oracle_tns"] == "test_tns"
    assert "output_dir" in cfg
    assert cfg["max_workers"] is None


def test_group_config(tmp_path):
    folder = tmp_path / "myhandle"
    folder.mkdir()
    (folder / "group.yaml").write_text("handle: myhandle\ndisplay_name: Foo\ntags: [a,b]\n")
    (folder / "query.sql").write_text("select 1")
    g = Group(str(folder))
    assert g.handle == "myhandle"
    assert g.display_name == "Foo"
    assert g.tags == {"a", "b"}
    assert "select" in g.read_query().lower()


def test_group_matches():
    class Dummy(Group):
        pass
    g = Group(str(tmp_path)) if False else None

    # create fake group
    tmp = tempfile.mkdtemp()
    cfg = {
        "handle": "h1",
        "display_name": "H1",
        "tags": ["t1", "t2"],
    }
    with open(os.path.join(tmp, "group.yaml"), "w") as f:
        yaml.safe_dump(cfg, f)
    with open(os.path.join(tmp, "query.sql"), "w") as f:
        f.write("select 1")
    g = Group(tmp)
    assert g.matches(names=["h1"])
    assert g.matches(tags=["t2"])
    assert not g.matches(names=["other"])


def test_group_generates_query_from_saved_builder_params(tmp_path):
    folder = tmp_path / "generated_group"
    folder.mkdir()
    cfg = {
        "handle": "generated_group",
        "display_name": "Generated Group",
        "tags": ["x"],
        "query_builder": {
            "mode": "by_role",
            "attributes_job_code": "000545",
            "attributes_department_id": "02SA23",
        },
    }
    (folder / "group.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    g = Group(str(folder))
    sql = g.read_query()
    assert "JOB_CODE = '000545'" in sql


def test_group_override_query_takes_precedence(tmp_path):
    folder = tmp_path / "override_group"
    folder.mkdir()
    cfg = {
        "handle": "override_group",
        "display_name": "Override Group",
        "tags": ["x"],
        "query_builder": {
            "mode": "by_role",
            "attributes_job_code": "000545",
        },
    }
    (folder / "group.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    (folder / "query.sql").write_text("SELECT USERNAME FROM manual_source", encoding="utf-8")
    g = Group(str(folder))
    assert g.read_query().strip() == "SELECT USERNAME FROM manual_source"


def test_remove_override_keeps_query_builder_params(tmp_path):
    base = tmp_path
    groups_dir = base / "groups"
    groups_dir.mkdir()
    group_dir = groups_dir / "keep_params"
    group_dir.mkdir()

    cfg = {
        "handle": "keep_params",
        "display_name": "Keep Params",
        "tags": [],
        "query_builder": {
            "mode": "by_role",
            "attributes_job_code": "000545",
        },
    }
    (group_dir / "group.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    (group_dir / "query.sql").write_text("SELECT USERNAME FROM override", encoding="utf-8")

    svc = GroupService(str(base))
    g = svc.get_group("keep_params")
    assert g is not None
    assert g.has_override_query()

    svc.update_group(group=g, query="")

    g2 = svc.get_group("keep_params")
    assert g2 is not None
    assert not g2.has_override_query()
    assert g2.config.get("query_builder", {}).get("attributes_job_code") == "000545"
