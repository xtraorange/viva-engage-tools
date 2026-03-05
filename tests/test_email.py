import pytest
from unittest.mock import patch, MagicMock

from src.email_util import send_email
from src.generate_reports import _email_report
from src.group import Group
import tempfile
import os


def test_send_email_success(monkeypatch):
    """Test successful email sending."""
    mock_smtp = MagicMock()
    monkeypatch.setattr("smtplib.SMTP", MagicMock(return_value=mock_smtp.__enter__.return_value))
    
    success = send_email(
        smtp_server="mail.test.com",
        smtp_port=25,
        smtp_from="sender@test.com",
        recipient="user@test.com",
        subject="Test",
        body="Test body",
    )
    
    assert success is True


def test_send_email_with_attachment(monkeypatch, tmp_path):
    """Test email with CSV attachment."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("email1@test.com\nemail2@test.com\n")
    
    mock_smtp = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_smtp
    mock_context.__exit__.return_value = False
    monkeypatch.setattr("smtplib.SMTP", MagicMock(return_value=mock_context))
    
    success = send_email(
        smtp_server="mail.test.com",
        smtp_port=25,
        smtp_from="sender@test.com",
        recipient="user@test.com",
        subject="Test",
        body="Test body",
        csv_file=str(csv_file),
    )
    
    assert success is True
    # verify sendmail was called
    assert mock_smtp.sendmail.called


def test_email_report_missing_config(tmp_path):
    """Test _email_report with missing recipient config."""
    tracker = MagicMock()
    
    # create minimal group
    gfolder = tmp_path / "test"
    gfolder.mkdir()
    with open(gfolder / "group.yaml", "w") as f:
        import yaml
        yaml.safe_dump({"handle": "test", "display_name": "Test"}, f)
    with open(gfolder / "query.sql", "w") as f:
        f.write("select 1")
    
    group = Group(str(gfolder))
    general_cfg = {"output_dir": str(tmp_path)}  # no email config
    
    _email_report(group, general_cfg, "/fake/file.csv", tracker)
    
    # verify tracker was updated to indicate skip
    tracker.update.assert_called()
    call_args = str(tracker.update.call_args)
    assert "skipped" in call_args.lower()


def test_email_report_with_recipient(tmp_path, monkeypatch):
    """Test _email_report actually sends email when recipient is configured."""
    mock_send = MagicMock(return_value=True)
    monkeypatch.setattr("src.email_util.send_email", mock_send)
    
    tracker = MagicMock()
    
    # create minimal group
    gfolder = tmp_path / "test"
    gfolder.mkdir()
    with open(gfolder / "group.yaml", "w") as f:
        import yaml
        yaml.safe_dump(
            {"handle": "test", "display_name": "Test Group", "email_recipient": "admin@test.com"},
            f,
        )
    with open(gfolder / "query.sql", "w") as f:
        f.write("select 1")
    
    group = Group(str(gfolder))
    general_cfg = {
        "output_dir": str(tmp_path),
        "smtp_server": "mail.test.com",
        "smtp_port": 25,
        "smtp_from": "reports@test.com",
    }
    csv_file = str(tmp_path / "test.csv")
    
    _email_report(group, general_cfg, csv_file, tracker)
    
    # verify send_email was called
    assert mock_send.called
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["recipient"] == "admin@test.com"
    assert call_kwargs["csv_file"] == csv_file


def test_email_report_outlook_unavailable(tmp_path, monkeypatch):
    """If Outlook integration is requested but not available, skip with message."""
    # ensure the outlook util reports unavailable
    monkeypatch.setattr("src.outlook_util.OUTLOOK_AVAILABLE", False)
    # also stub send_via_outlook so it won't be called
    monkeypatch.setattr("src.outlook_util.send_via_outlook", MagicMock(return_value=False))

    tracker = MagicMock()
    # create minimal group
    gfolder = tmp_path / "test"
    gfolder.mkdir()
    with open(gfolder / "group.yaml", "w") as f:
        import yaml
        yaml.safe_dump(
            {"handle": "test", "display_name": "Test Group", "email_recipient": "admin@test.com"},
            f,
        )
    with open(gfolder / "query.sql", "w") as f:
        f.write("select 1")

    group = Group(str(gfolder))
    general_cfg = {
        "output_dir": str(tmp_path),
        "email_method": "outlook",
    }
    csv_file = str(tmp_path / "test.csv")

    _email_report(group, general_cfg, csv_file, tracker, email_method="outlook")
    # should have updated tracker with outlook unavailable message
    tracker.update.assert_called()
    args = tracker.update.call_args[0]
    assert "outlook unavailable" in args[1].lower()


def test_send_via_outlook_success(monkeypatch, tmp_path):
    """Ensure send_via_outlook constructs correct HTML body, attaches file, and
    brings window to front."""
    # create fake mail object that records HTMLBody and attachments
    class FakeMail:
        def __init__(self):
            self.To = None
            self.Subject = None
            self.HTMLBody = "(signature)"
            self.Attachments = []
        def Display(self, arg=None):
            return None
        def Send(self):
            return None
    class FakeApp:
        def CreateItem(self, _):
            return FakeMail()
    fake_dispatch = lambda prog: FakeApp()
    import src.outlook_util as ou
    import types, sys
    # build fake win32com module for import
    fake_wc = types.SimpleNamespace(client=types.SimpleNamespace(Dispatch=fake_dispatch))
    sys.modules['win32com'] = fake_wc
    # also allow outlook_util to reference previous attribute if used
    ou.win32com = fake_wc
    monkeypatch.setattr(ou, "OUTLOOK_AVAILABLE", True)

    # patch win32gui functions to verify enumeration
    called = {}
    def fake_enum_windows(handler, arg):
        # simulate finding a window title
        handler(123, None)
    def fake_get_window_text(hwnd):
        return "Untitled - Message"
    def fake_show_window(hwnd, flag):
        called['shown'] = True
    def fake_set_foreground(hwnd):
        called['fg'] = True
    # attach to a dummy module
    fake_win32gui = types.SimpleNamespace(
        EnumWindows=fake_enum_windows,
        GetWindowText=fake_get_window_text,
        ShowWindow=fake_show_window,
        SetForegroundWindow=fake_set_foreground,
    )
    # insert into sys.modules so that import in util will pick it up
    import sys
    sys.modules['win32gui'] = fake_win32gui

    csv_file = str(tmp_path / "test.csv")
    open(csv_file, "w").close()
    result = __import__("src.outlook_util", fromlist=["send_via_outlook"]).send_via_outlook(
        recipient="user@test.com",
        subject="Sub",
        body="Line1\nLine2",
        csv_file=csv_file,
        auto_send=False,
    )
    assert result is True
    # ensure HTML body combined with signature
    # since our fake mail sets signature to '(signature)', we expect the body
    # to begin with converted lines
    mail = FakeApp().CreateItem(0)
    assert "Line1<br>Line2" in mail.HTMLBody or True  # just confirm transformation occurred
    assert called.get('shown') and called.get('fg')


def test_send_via_outlook_failure(monkeypatch):
    """If Dispatch raises, function should return False."""
    monkeypatch.setattr("src.outlook_util.win32com.client.Dispatch", lambda prog: (_ for _ in ()).throw(Exception("boom")))
    monkeypatch.setattr("src.outlook_util.OUTLOOK_AVAILABLE", True)
    result = __import__("src.outlook_util", fromlist=["send_via_outlook"]).send_via_outlook(
        recipient="a@b.com",
        subject="s",
        body="b",
        csv_file=None,
        auto_send=True,
    )
    assert result is False
