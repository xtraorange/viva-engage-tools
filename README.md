# Viva Engage Member List Generator

**jampy-engage** is a user-friendly tool for generating and emailing member lists from Viva Engage communities. Manage everything through a modern web interface or use the command-line interface for automation.

## ⚡ Quick Start (Recommended)

### One-Line Installation

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/xtraorange/jampy-engage/main/install.ps1 | iex
```

**macOS/Linux (bash):**
```bash
curl -fsSL https://raw.githubusercontent.com/xtraorange/jampy-engage/main/install.sh | bash
```

**Manual Installation:**
1. Install [Python 3.10+](https://www.python.org/) (make sure to check "Add Python to PATH")
2. Install [Git](https://git-scm.com/)
3. Clone the repository:
   ```bash
   git clone https://github.com/xtraorange/jampy-engage.git
   cd jampy-engage
   ```
4. Create a virtual environment:
   ```bash
   # Windows
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   
   # macOS/Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```
5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
6. Start the application:
   - **Windows:** Double-click `start.bat` or run `.\start.ps1` in PowerShell
   - **macOS/Linux:** Run `python run_reports.py`
   
   The start scripts automatically:
   - Activate the virtual environment
   - Start the Flask server
   - Open your browser to http://localhost:5000

The application is now ready to use!

## 📖 Using the Web Interface (Recommended)

The web interface provides an easy-to-use dashboard for managing everything.

### Navigation
- **Generate** - Select groups/tags and generate member lists with optional email delivery
- **App Settings** - Configure database, output directory, email settings, email templates
- **Groups** - Create, edit, and delete groups with SQL queries
- **Tags** - Manage tags and add new ones across multiple groups
- **Email Templates** - Customize email subject and body
- **Updates** - Check for and install application updates
- **Backup/Restore** - Back up your configuration and restore it later

### Workflow

#### 1. Configure App Settings
Navigate to **App Settings** to configure:
- **Database Settings**: Oracle TNS connection string
- **Output Settings**: Where to save CSV files and how many jobs to run in parallel
- **Email Settings**: 
  - SMTP: Email via SMTP server (cross-platform)
  - Outlook: Send via Outlook application (Windows only)
- **SMTP Settings**: Server, port, TLS, sender address

**Tooltips:** Hover over the `?` badges next to each field to see helpful information.

#### 2. Manage Groups
Navigate to **Groups** to:
- **View all groups** with their display names
- **Create new groups** - Click "+ New Group" button
  - Enter a unique handle (e.g., `sales_team`)
  - Set display name and tags
  - Enter your SQL query, or click **"🔨 Use Query Builder"** to build one interactively
  - Optional: set a group-specific email recipient
- **Edit groups** - Click "Edit" to modify SQL query, display name, tags, or email recipient
- **Delete groups** - Click "Delete" (with confirmation)

#### 2a. Using the SQL Query Builder
The SQL Query Builder helps you construct complex hierarchical queries without writing SQL:
- **By Person Mode**: Search for an employee and automatically build their hierarchy with supervisors and direct reports
- **By Role Mode**: Select hierarchy roots by job code/title, business unit, company, branch, or department
- **All Employees Mode**: Start from all active employees and apply optional filters
- **Filters**: Apply additional filters to the results (job titles, departments, etc.)
- **Preview**: SQL updates as you type; use **Test Query** to validate result count
- Click **"Accept This Query"** to save builder parameters to the group
- Use **"Edit SQL Manually"** to create an optional override SQL script (`query.sql`) for that group

#### 3. Manage Tags
Navigate to **Tags** to:
- **View all tags** and which groups have them
- **Create new tags** - Click "+ New Tag"
  - Enter tag name
  - Select which groups to add the tag to
  - Click "Create Tag"
- **Delete tags** - Click "Delete" to remove tag from all groups

#### 4. Customize Email Templates
Navigate to **Email Templates** to:
- **Standard Email** - Template for emails sent to group recipients
- **Override Email** - Template for bulk emails sent to a single address
- Use template variables like `{group_name}`, `{date}`, `{count}`, etc.
- See available variables listed on the same page

#### 5. Generate and Send Reports
Navigate to **Generate** to:
1. **Select groups** - Check individual groups or filter by tags
2. **Choose email option**:
   - **No email** - Just generate CSV files
   - **Email to configured recipients** - Send each group's CSV to their configured recipient
   - **Email all to specific address** - Send all CSVs to one email address
3. **Click Generate** - Reports will be generated and optionally emailed
4. **Monitor progress** - Watch real-time status on the status page

#### 6. Backup and Restore
- **Backup** - Click "Backup" in the top navigation to download a zip file of all configurations
- **Restore** - Click "Restore" to upload a previously saved backup

##  Application Updates
The web UI includes an automatic update checker that reads the version directly from GitHub:
- **Automatic checking**: Checks GitHub for version updates once per day
- **Manual checking**: Click "Updates" in the top navigation, then "Check again" to force a fresh check
- **Updates page**: Shows your current version, latest release, and release notes
- **One-click updates**: Click "Update now" to automatically pull latest code and reinstall dependencies

The application enters "updating" mode while installing - most pages become disabled. After the update completes, restart the server to load the new code.

**How it works:** The update checker reads `config/version.yaml` directly from the GitHub repository, so any version change is detected immediately - no need to concern yourself with release markings or API caching issues.

## 🔧 Command-Line Interface (for automation)

The CLI is useful for automating report generation via task scheduler or cron jobs.

```bash
# Launch web interface (default)
python run_reports.py

# Interactive CLI mode
python run_reports.py --cli

# Generate specific groups by handle
python run_reports.py --cli sales_team accounting_team

# Generate groups by number (from list command)
python run_reports.py --cli 1 2 3

# Generate groups by tag
python run_reports.py --cli important

# Send emails to configured recipients
python run_reports.py --cli sales_team --email

# Send all reports to specific email
python run_reports.py --cli sales_team --email user@example.com

# List available groups with indices
python run_reports.py --cli list
```

## 📋 Configuration Directory Structure

```
jampy-engage/
├── config/
│   ├── general.yaml              # App settings (database, email, output)
│   ├── email_template.yaml       # Standard email template
│   └── email_template_override.yaml
├── groups/                       # Each group is a folder
│   ├── sales_team/
│   │   ├── group.yaml            # Group config (name, tags, recipient)
│   │   └── query.sql             # Optional manual SQL override (takes precedence if present)
│   └── accounting_team/
│       ├── group.yaml
│       └── query.sql
├── src/                          # Application code (don't modify)
│   ├── run_reports.py           # Main entry point module
│   ├── generate_reports.py      # CLI and processing logic
│   ├── services/                # Business logic services
│   │   ├── config_service.py    # Configuration management
│   │   ├── group_service.py     # Group CRUD operations
│   │   ├── report_service.py    # Report generation logic
│   │   └── email_service.py     # Email sending functionality
│   ├── ui/                      # Web interface package
│   │   ├── __init__.py          # Flask app setup
│   │   ├── utils.py             # UI utilities
│   │   ├── routes/              # Flask route modules
│   │   │   ├── main.py          # Main web routes
│   │   │   ├── groups.py        # Group management routes
│   │   │   ├── tags.py          # Tag management routes
│   │   │   ├── api.py           # AJAX API endpoints
│   │   │   └── updates.py       # Update/backup routes
│   │   └── templates/           # Web UI templates
│   ├── utils/                   # Utility functions
│   │   ├── file_utils.py        # File operations
│   │   └── validation.py        # Input validation
│   ├── tests/                   # Test files
│   ├── email_util.py
│   ├── db.py
│   └── ...
├── run_reports.py               # Main entry point (wrapper)
├── docs/                        # Documentation and misc files
└── requirements.txt             # Python dependencies
```

## 🔐 Security Notes

- Store your backups securely - they contain database connection strings
- Use app-specific or service account credentials for SMTP
- Ensure proper access controls on the machine running the application
- CSV files may contain sensitive member data - secure your output directory

## ❓ Troubleshooting

### "Python not found"
Make sure to check "Add Python to PATH" during Python installation, or reinstall Python.

### Database connection errors
Check your Oracle TNS setting in **App Settings**. Test the connection with your Oracle client tools first.

### Emails not sending
1. Check **App Settings** - verify SMTP server, port, and credentials
2. For Outlook: ensure the settings app is installed and you're running from Windows
3. Check email logs in the status page during generation

### Groups not appearing
Ensure you're in the correct working directory where `groups/` folder exists.

## 🤝 Support

For issues or feature requests, please visit the [GitHub repository](https://github.com/xtraorange/jampy-engage).

## 📝 Features

- 🎨 **Modern Web UI** - No command-line needed for regular use
- 📊 **SQL Query Builder** - Define member lists with custom queries
- 🏷️ **Tag System** - Organize groups by tags and batch-generate
- 📧 **Email Integration** - Support for SMTP and Outlook
- 📁 **Batch Processing** - Parallel job execution for performance
- 💾 **Backup/Restore** - Easy configuration backup and recovery
- 🔄 **CLI Automation** - Use via cron jobs or task scheduler
- 📈 **Real-time Progress** - Watch reports generate in real-time
- 🔄 **Auto-Updates** - Built-in update checker with one-click updates

## 🔧 Version Management

The application version is stored in `config/version.yaml`:

```yaml
version: "0.2.0"
repository: "xtraorange/jampy-engage"
repository_url: "https://github.com/xtraorange/jampy-engage"
```

**To release a new version:**
1. Update the `version` field in `config/version.yaml`
2. Commit and push to GitHub (on any branch, typically `main`)
3. Users will automatically see the update available the next time they check (or click "Check again" on the Updates page)
4. Optional: Create a GitHub release tag and add release notes for additional visibility

The update checker reads this file directly from GitHub, so changes are detected immediately without any caching delays or release marking requirements.


TODO:
 - The override message box on group edit is still formatted where it has a lot of top padding or a couple extra lines before the actual message.  This just appears strange.
 - I think we could make the formatting for the parameters on the group edit page much nicer looking.  Instead of being inside a monospace box, lets just give it a UI element box (not a text box) and then use tags for each parameter like we do on the sql builder page.
 - Let's unify the look of the UI to be the same as the SQL Query Builder look... the boxes and headers within the top of the boxes, etc.  Obviously this will need to be adapted from page to page, it won't always make sense... but let's try for consistency in the look.  It looks nicer than any of the other pages.  Let's also use a unified color scheme (not the colors on the sql builder page) based on a popular simple color scheme (you pick, nothing outlandish).  I also wouldn't mind if we found a popular pre-themed dashboard for our css library (like the material dashboard) and used it's style.
 - Purely for fun, I'd like to track statistics on everything in the app and have our landing page be a dashboard with some nice graphs and such (using the template mentioned previously).  We should have a way to reset the stats so that when I'm done testing I can reset everything (probably on the settings page).  We should track generation times, reports generated, which report has the most generations, etc.  Please come up with some interesting things to track. Even just how many reports are available.
 - Please update the tests and the documentation, run the tests, and correct any issues.
 - Please suggest other features that might be helpful given the general purposes of this app!