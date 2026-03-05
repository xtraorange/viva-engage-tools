# Viva Engage Member List Generator

This tool generates email lists for Viva Engage communities based on configurable
SQL queries.  Each community is defined by a unique handle and has its own folder
containing an SQL script and configuration file describing display name, tags,
and optional output location.

## Features

- Modular configuration per community
- Concurrent execution of SQL queries
- Clean CLI with interactive prompts
- CSV output with filenames like `handle (Display Name) - YY-MM-DD.csv`
- Optional email delivery of generated CSVs (SMTP or Outlook)
- Extensible via tags and future features

## Getting Started

1. Install dependencies from `requirements.txt` (including the `jampy-db` library).
2. Edit `config/general.yaml` to match your environment.
3. Add community directories under `groups/` containing `group.yaml` and
   `query.sql`.
4. Run the script via module or the convenient root entrypoint:
   ```bash
   # Interactive: prompts you to choose groups by number, handle, or tag
   python run_reports.py
   
   # By handle: generate CSV(s) for specified group(s)
   python run_reports.py my_community
   python run_reports.py group1 group2
   
   # By tag: generate CSVs for all groups matching a tag
   python run_reports.py example test
   
   # List available groups (to see numeric indices)
   python run_reports.py list
   
   # By number: generate CSV(s) using indices (from 'list' command)
   python run_reports.py 1
   python run_reports.py 1 2 3
   
   # With email: generate and email to configured recipients
   python run_reports.py my_community --email
   python run_reports.py 1 --email
   ```

The progress display is updated continually so you can watch each
report's state in real time.  You'll see lines such as:

```
community_a: generating member list (1/5)
community_b: querying database
community_c: writing CSV
Completed 2/5 (40% )
```

and later steps like "preparing email" or "sending email" will
appear as tasks advance.

### Database Configuration

This tool uses the [jampy-db](https://github.com/xtraorange/jampy-db) library for
connections.  Set `oracle_tns` in `config/general.yaml` for the TNS alias to use.
Additional connection options (e.g. `client_folder`, `config_dir`) may be added
and will be forwarded to the `oracle_thick_external` profile.  See the
`profiles/oracle_thick_external.py` file in the package for more details.

### Email Configuration (Optional)

The generator supports both **SMTP** and **Outlook** delivery.  Outlook
integration requires a Windows environment and the `pywin32` package.
Install dependencies before using it:

```bash
pip install -r requirements.txt   # includes pywin32
```

and ensure `email_method` in `config/general.yaml` is set to `"outlook"`
(or leave as `"smtp"` to continue using SMTP).

To enable SMTP delivery (works cross‑platform):

1. Configure SMTP settings in `config/general.yaml`:
   ```yaml
   smtp_server: "mail.fastenal.com"
   smtp_port: 25
   smtp_use_tls: false
   smtp_from: "reports@fastenal.com"
   # Set a default recipient, or leave empty to use per-group recipients
   # email_recipient: "admin@fastenal.com"
   ```

2. Add recipient(s):
   - Globally: set `email_recipient` in `config/general.yaml` (one person receives all CSVs)
   - Per-group: set `email_recipient` in each group's `group.yaml` (specific contact for that group)
   - Group config takes precedence over global config

3. Run with the `--email` flag:
   ```bash
   python run_reports.py my_community --email
   ```

