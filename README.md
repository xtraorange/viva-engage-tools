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

Todo:
 - Filters should begin on a new line after the word filters on the people source blocks in the query builder.
 - For both the filters and the By Role block, I want to reorder the attributes.  First should be job tit;e/code, then department id, then they can be in the order they're currently in from there.
 - When building a By Role block, I'd like to have a special feature: I'd like to be able to hit a button near the top to do a person search.  It would open some sort of modal which would allow me to first use the person search mechanism to locate someone or multiple people.  Once the first person is located, a table would appear with rows of attributes matching the attributes we have on the by role block (the things we identify a role with) - it would be nice if these were attached to each other in such a way that if it gets removed from one we also remove it from the other, but maybe that's too complicated.  TThe table would begin with the first column as check boxes, and the second column would be the attribute we're looking at.  Next we'd have a column for each person selected and the value they have for that particular attribute.  Finally, the last column would be the number of users that share that attribute.  The idea here is to help me identify what makes this person's role unique... usually it will be job title and department id combined.  Finally, underneath that, I want the same box we have in the block itself, the Current Hierarchy Leader Matches (but we can rename it), showing if we used the parameters that have been checked, how many matches and who.  This should update each time we check or uncheck a box.  At the bottom we should have a "Use These Parameters" button, which transfers the checked boxes into the boxes on the block as though they had been searched (so as tags, ready to go), and a cancel button which just closes the modal.  Let's be careful to make sure we're matching the way we display and search these parameters, since some are more complicated (like Job title/code).. we want to display the same way, and we also don't want to break anything in the search either in the modal or when we transfer it... so take extra care to make srue we're matching things up identically.