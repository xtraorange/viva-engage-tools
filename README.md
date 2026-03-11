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
- **Dashboard** - View generation analytics and operational metrics
- **Generate Reports** - Select groups and configure email options to generate reports
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

#### 5. Dashboard - View Analytics
Navigate to **Dashboard** (home page) to:
1. **Review analytics** - Track total reports generated, average run duration, run health, and per-group generation trends
2. **Use charts** - Visualize the most-used reports and overall run outcomes
3. **View KPI cards** - See reports available, total generations, average runtime, and most-generated report
4. **Launch report generation** - Click the "Generate Reports" button to proceed to the generation page

The app tracks operational metrics in `config/stats.yaml`, including run requests, reports generated, run durations, most-generated report, and available report count.

#### 5a. Generate Reports
Navigate to **Generate Reports** to:
1. **Select groups** - Choose individual groups or filter by tags
2. **Choose email option**:
   - **No email** - Just generate CSV files
   - **Email to configured recipients** - Send each group's CSV to their configured recipient
   - **Email all to specific address** - Send all CSVs to one email address
3. **Click Start** - Reports will be generated and optionally emailed
4. **Monitor progress** - You'll be taken to the status page to watch real-time progress

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
│   │   ├── email_service.py     # Email sending functionality
│   │   └── stats_service.py     # Dashboard statistics tracking
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
- 📊 **Dashboard Analytics** - KPI cards and charts for generation trends
- 💾 **Backup/Restore** - Easy configuration backup and recovery
- 🔄 **CLI Automation** - Use via cron jobs or task scheduler
- 📈 **Real-time Progress** - Watch reports generate in real-time
- 🔄 **Auto-Updates** - Built-in update checker with one-click updates
- 🎨 **Material Design Theme** - Beautiful Material Design interface with smooth interactions
- 🔍 **Advanced Search** - Search and filter groups and tags in real-time
- 📄 **Dedicated Generate Page** - Separate page for report generation workflow

## 💡 Additional Helpful Features

- **Built-in Scheduling** - Create recurring runs from the UI without external schedulers
- **Change Detection Reports** - Attach added/removed members compared to prior run
- **Delivery Audit Log** - Keep history of every generation and email outcome
- **Alerting Thresholds** - Notify when report counts change sharply
- **Role-based Permissions** - Separate admin actions from run-only actions
- **Dashboard Exports** - Download metrics snapshots as CSV/PDF

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

Todo:
 - After generation is commplete, the "Back to Generate" button takes you instead to the dashboard.
 - On the generate reports screen, the estimated runtime isn't making sense to mme... I have 2 groups select, with 1.2 and 1.1 seconds average for them.  The estimated run time is 1.2... shouldn't it be 2.3?  Or is it assuming some multi-threading type operations?
 - On the generate reports screen, I think we can make the number of groups selected, and the estimate and number unable to add to the estimate a bit cleaner.  They don't need to be in the same place... maybe the top shows the number of groups selected and the time estimate is by the start generation button?  Mayybe we need soem different formatting?
 - On the generate reports screen, let's put the selected groups inside of a scrolling box so the start generation button doesn't get below the screen and require weird scrolling things.
 - When we load the adhoc name matcher file, there should probably be a loading screen with feedback.  Similar to how we do the generation status screen.  Something about what it's currently working on (maybe big picture and individual... so big picture might be loading file or searching names, while it also shows which name it's working on)... basically anything that takes any time should have a status, even getting ready to display everything.  Also, let's add the same loading wheel as the update screen uses.  Let's also add that to the report generation screen.
 - On the query builder screen, the "Only Direct Reports" checkbox still appears inside the current hierarchy leader matches box on the By Role tab... it should be outside of that box, above the box, below department IDs.  Since we called it "options" on the group edit screen, let's add a label of Options before it on both by person (which should probably also include exclude the selected person from the results) and by role.