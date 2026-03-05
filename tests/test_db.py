from src.db import DatabaseExecutor


class DummyClient:
    def __init__(self):
        self.queries = []

    def query(self, sql, return_type=None, run_async=True):
        class Job:
            def __init__(self, sql):
                self._sql = sql

            def result(self):
                return [("a@x.com",)]

        self.queries.append(sql)
        return Job(sql)

    def close(self):
        pass


def test_executor(monkeypatch):
    # patch jampy_db.create to return dummy client
    import jampy_db

    monkeypatch.setattr(jampy_db, "create", lambda profile, **props: DummyClient())
    execu = DatabaseExecutor("dummy")
    rows = execu.run_query("select 1")
    assert rows == [("a@x.com",)]
    execu.write_csv(rows, None, "./temp.csv")
    assert execu.client.queries
    execu.close()


def test_username_domain(tmp_path, monkeypatch):
    # patch executor to simulate returning rows/dicts
    from src.generate_reports import process_group
    class DummyExec:
        def __init__(self):
            pass
        def run_query(self, q):
            return [{"USERNAME": "bob"}, ("alice",)]
        def write_csv(self, rows, headers, out):
            # rows should be collapsed single-item tuples containing email
            assert rows == [("bob@fastenal.com",), ("alice@fastenal.com",)]
    tracker = type("T", (), {"update": lambda self,h,m:None, "increment": lambda self,h:None})()
    cfg = {"output_dir": str(tmp_path)}
    gfolder = tmp_path / "g"
    gfolder.mkdir()
    # create minimal group config
    with open(gfolder / "group.yaml", "w") as f:
        import yaml
        yaml.safe_dump({"handle": "g", "display_name": "G"}, f)
    with open(gfolder / "query.sql", "w") as f:
        f.write("select")
    from src.group import Group
    group = Group(str(gfolder))
    execu = DummyExec()
    # provide dummy job numbering but they are unused in this unit test
    process_group(group, cfg, execu, tracker, should_email=False, job_num=1, job_total=1)
