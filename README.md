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
6. Run the application:
   ```bash
   python run_reports.py
   ```

Open your browser to **http://localhost:5000** and you're ready to go!

## 📖 Using the Web Interface (Recommended)

The web interface provides an easy-to-use dashboard for managing everything.

### Navigation
- **Generate** - Select groups/tags and generate member lists with optional email delivery
- **App Settings** - Configure database, output directory, email settings, email templates
- **Groups** - Create, edit, and delete groups with SQL queries
- **Tags** - Manage tags and add new ones across multiple groups
- **Email Templates** - Customize email subject and body
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
  - Paste your SQL query
  - Optional: set a group-specific email recipient
- **Edit groups** - Click "Edit" to modify SQL query, display name, tags, or email recipient
- **Delete groups** - Click "Delete" (with confirmation)

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

## 🔧 Command-Line Interface (for automation)

## 🔄 Built‑in Update Checker
The web UI now checks GitHub for new releases once per day. If a newer
version is available you'll see a banner on the **App Settings** page along
with release notes. Click **Update now** to pull the latest code and install
updated dependencies. The application will enter a temporary "updating" mode
— most pages become disabled until you restart the server.

Updates are performed by running `git pull` in the installation directory and
re-installing requirements. Because Python must reload the code, you'll need to
restart the process when the update completes. The installer scripts (`install.sh`
and `install.ps1`) can be used again to perform the update from the command
line.

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
│   │   └── query.sql             # SQL query for member list
│   └── accounting_team/
│       ├── group.yaml
│       └── query.sql
├── templates/                    # Web UI templates (don't modify)
├── src/                          # Application code (don't modify)
│   ├── generate_reports.py
│   ├── ui.py
│   ├── email_util.py
│   ├── db.py
│   └── ...
├── run_reports.py               # Main entry point
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

