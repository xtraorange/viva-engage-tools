# Viva Engage Member List Generator

jampy-engage generates Viva Engage membership CSV reports from Oracle data, with optional email delivery.

You can run it in either mode:
- Web UI (recommended for daily use)
- CLI (recommended for scheduled automation)

## Quick Start

### One-line install

Windows (PowerShell):
```powershell
irm https://raw.githubusercontent.com/xtraorange/jampy-engage/main/install.ps1 | iex
```

macOS/Linux (bash):
```bash
curl -fsSL https://raw.githubusercontent.com/xtraorange/jampy-engage/main/install.sh | bash
```

### Manual install

1. Install Python 3.10+
2. Clone this repository:
```bash
git clone https://github.com/xtraorange/jampy-engage.git
cd jampy-engage
```
3. Create and activate a virtual environment:
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```
4. Install dependencies:
```bash
pip install -r requirements.txt
```
5. Start the app:
```bash
python run_reports.py
```

On Windows, you can also use start.ps1 or start.bat.

## Web UI Overview

Primary navigation:
- Dashboard
- Generate
- Groups
- Tags
- Settings

Additional pages are available from Settings:
- Ad Hoc Name Matcher
- Email Templates
- Updates
- Backup Configuration
- Restore Configuration

## What the App Does

### Group management
- Create, view, edit, and delete groups
- Configure display name, tags, email recipient, and output directory override
- Define query input using either:
  - Query Builder parameters
  - Manual SQL override (query.sql)
- Persist preferred query mode (builder/manual) per group

### Query Builder
- Build hierarchy queries using block-based configuration:
  - Hierarchy by person
  - Hierarchy by role attributes
  - Filtered population
  - Manual individuals
- Apply filters such as job title, BU, company, branch, and department
- Preview generated SQL
- Test query row count
- Accept builder output back into group editing

### Report generation
- Select groups directly and/or by tags
- Generate CSV reports in parallel
- Optional email delivery:
  - To each group's configured recipient
  - To one override recipient for all selected reports
- Track progress on status page
- View generated report content from status page with in-page pagination

### Tags
- Create, edit, and delete tags
- Assign tags to multiple groups
- Browse group membership for each tag

### Settings
- Configure Oracle connection (TNS)
- Configure output directory and worker count
- Configure email settings:
  - SMTP settings
  - Outlook mode (Windows)
- Restart app from UI
- Reset dashboard statistics

### Email templates
- Manage standard and override email templates

### Ad Hoc Name Matcher
- Upload a CSV of names
- Search/match employees
- Review and adjust selections
- Export enriched results as CSV

### Updates
- Check latest version from GitHub
- Show latest version metadata
- Perform update/force-update workflow
- Stream update progress and request restart

### Backup and restore
- Download zip backup of config and groups
- Restore from backup zip

## CLI Usage

Run CLI mode:
```bash
python run_reports.py --cli
```

Examples:
```bash
# list available groups
python run_reports.py --cli list

# run selected handles
python run_reports.py --cli sales_team accounting_team

# run selected numeric indices
python run_reports.py --cli 1 2 3

# run by tag
python run_reports.py --cli leadership

# email to configured recipients
python run_reports.py --cli sales_team --email

# email all selected reports to one address
python run_reports.py --cli sales_team --email user@example.com
```

## Project Structure

```text
jampy-engage/
├── config/
├── groups/
├── src/
│   ├── services/
│   ├── ui/
│   │   ├── routes/
│   │   ├── templates/
│   │   └── static/
│   ├── tests/
│   └── ...
├── run_reports.py
└── requirements.txt
```

## Security Notes

- Backups may contain sensitive configuration values
- Report CSVs may contain sensitive member data
- Protect output folders and backup files appropriately

## Version Management

Version metadata is stored in config/version.yaml.

To release a new version:
1. Update config/version.yaml
2. Commit and push
3. Users can check from the Updates page

## Support

For issues and feature requests, use:
https://github.com/xtraorange/jampy-engage

TODO:
 - Introduce "Test Query" function.  The test query function should open a modal for testing the "current" query from a query builder.  So if you're inside the query builder, it's the on your currently configuring.  If you're on the group view and it's in query builder mode (not manual override) it's that one.  When the modal opens, it should show two things: 1. A count of records for that query.  And 2. a table of the results.  However, in this case, in addition to the normal e-mails, the query should also select (and display in the table) the name and title of the selected people.  It should paginate the results over 100.  A button to run the query tester should be on the group view, and on the query builder page as another action button.
  - The group page is kind of a mess of buttons right now.  The query config is really the main problem.  It has 3 buttons in query mode, and we're addign another, and 2 actions in the action menu.  Let's simplify.  Instead of showing open query builder and edit query in manual sql mode buttons, and then a different edit query button when you're in manual mode, let's just use "Edit Query" in the bottom right in blue regardless of mode.  If in query builder mode, that opens the query builder.  When in manual it lets you edit the sql.  Then on the left side (left aligned) of the Edit Query button (only when not in manual sql mode), we can use the theme of the "Open Query Builder" and display the new Test Query button.