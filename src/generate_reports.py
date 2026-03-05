import argparse
import glob
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List

from .config import load_general_config
from .db import DatabaseExecutor, ProgressTracker
from .group import Group


def discover_groups(base_path: str) -> List[Group]:
    pattern = os.path.join(base_path, "groups", "*")
    folders = [p for p in glob.glob(pattern) if os.path.isdir(p)]
    return [Group(folder) for folder in folders]


def prompt_choice(groups: List[Group]) -> tuple:
    """Prompt user to select groups and optionally email.
    
    Supports --email flag with optional override address:
    - "1 2 3" → select groups 1, 2, 3
    - "1 --email" → select group 1, email to configured recipients
    - "1 --email user@example.com" → select group 1, email to override address
    
    Returns:
        Tuple of (selected_groups, should_email, override_email)
    """
    print("Available groups:")
    for idx, g in enumerate(groups, start=1):
        print(f"{idx}. {g.handle} ({g.display_name})")
    choice = input(
        "Enter numbers (comma-separated), handles, or tag names (optionally add --email): "
    )
    
    # Parse --email flag and optional override
    should_email = False
    override_email = None
    tokens = choice.split()
    
    # Look for --email in tokens
    if "--email" in tokens:
        should_email = True
        idx = tokens.index("--email")
        # Check if next token is an email address (contains @ and no spaces)
        if idx + 1 < len(tokens) and "@" in tokens[idx + 1]:
            override_email = tokens[idx + 1]
            tokens.pop(idx + 1)  # remove the email
        tokens.pop(idx)  # remove --email
    
    # Rejoin remaining tokens and split by comma for group selection
    choice = " ".join(tokens)
    items = [i.strip() for i in choice.split(",") if i.strip()]
    
    # try to match by handle or tag
    selected = []
    for item in items:
        if item.isdigit():
            idx_group = int(item) - 1
            if 0 <= idx_group < len(groups):
                selected.append(groups[idx_group])
        else:
            for g in groups:
                if g.handle == item or item in g.tags:
                    selected.append(g)
    
    return list(dict.fromkeys(selected)), should_email, override_email  # remove duplicates


def main():
    parser = argparse.ArgumentParser(description="Generate Viva Engage email lists.")
    parser.add_argument("names", nargs="*", help="group handles or tags (or 'list')")
    parser.add_argument(
        "--email",
        nargs="?",
        const=True,
        metavar="EMAIL",
        help="email the generated CSVs; optionally specify override recipient (e.g., --email admin@company.com)",
    )
    args = parser.parse_args()

    base = os.getcwd()
    general_cfg = load_general_config(os.path.join(base, "config", "general.yaml"))
    groups = discover_groups(base)

    # Parse email option: determines if we should email and to what address
    override_email = None
    should_email = False
    if args.email:
        should_email = True
        # args.email is True if --email with no arg, or a string if --email ADDRESS
        if isinstance(args.email, str):
            override_email = args.email

    if not args.names:
        selected, interactive_should_email, interactive_override = prompt_choice(groups)
        # Interactive prompt can override email settings
        if interactive_should_email:
            should_email = True
            if interactive_override:
                override_email = interactive_override
    elif len(args.names) == 1 and args.names[0].lower() == "list":
        print("Groups and tags:")
        for g in groups:
            print(f"{g.handle} \t{g.display_name}\t tags={','.join(g.tags)}")
        sys.exit(0)
    else:
        # decide whether passed names contain tags, handles, or numeric indices
        selected_set = set()
        for token in args.names:
            token = token.strip()
            # check if token is a numeric index
            if token.isdigit():
                idx = int(token) - 1  # convert to 0-indexed
                if 0 <= idx < len(groups):
                    selected_set.add(groups[idx].handle)
            elif any(g.handle == token for g in groups):
                selected_set.add(token)
            else:
                # try as tag: find all groups with this tag
                for g in groups:
                    if token in g.tags:
                        selected_set.add(g.handle)
        selected = [g for g in groups if g.handle in selected_set]

    if not selected:
        print("No groups matched input; exiting.")
        sys.exit(1)

    executor = DatabaseExecutor(general_cfg.get("oracle_tns"))
    max_workers = general_cfg.get("max_workers")
    if max_workers is None:
        max_workers = os.cpu_count() or 4

    tracker = ProgressTracker(len(selected))
    futures = []
    csv_files = []  # collect CSV paths when using override_email

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for idx, g in enumerate(selected, start=1):
            tracker.update(g.handle, "queued")
            future = pool.submit(
                process_group,
                g,
                general_cfg,
                executor,
                tracker,
                should_email=should_email,
                override_email=override_email,
                job_num=idx,
                job_total=len(selected),
            )
            futures.append((future, g.handle if override_email else None))
        for fut, handle_info in futures:
            try:
                csv_path = fut.result()
                if override_email and csv_path:
                    # collect CSVs for bulk sending
                    csv_files.append(csv_path)
            except Exception as e:
                print(f"Error in a task: {e}")
    # clean up the database client
    try:
        executor.close()
    except Exception:
        pass
    
    # if using override email, send all CSVs in one email
    if override_email and csv_files:
        date_str = datetime.now().strftime("%y-%m-%d")
        groups_list = "\n".join([f"  - {os.path.basename(f)}" for f in csv_files])
        _send_override_email(
            override_email,
            general_cfg,
            csv_files,
            groups_list,
            date_str,
            len(selected),
        )
    
    print("All done.")


def process_group(
    group: Group,
    general_cfg: dict,
    executor: DatabaseExecutor,
    tracker: ProgressTracker,
    should_email: bool = False,
    override_email: str = None,
    job_num: int = 0,
    job_total: int = 0,
) -> str:
    """Process a single group: query, export CSV, and optionally email.
    
    Args:
        job_num: 1-based index of this job within the selected groups.
        job_total: total number of groups being processed.

    Returns:
        Path to the generated CSV file, or None if an error occurred.
    """
    handle = group.handle
    tracker.update(handle, f"generating member list ({job_num}/{job_total})")
    query = group.read_query()
    fullpath = None
    try:
        tracker.update(handle, "querying database")
        rows = executor.run_query(query)
        tracker.update(handle, f"fetched {len(rows)} rows")
        # append domain to USERNAME column if present, then collapse to single
        # email value per row (no header).
        emails = []
        for r in rows:
            email = None
            if isinstance(r, dict):
                # grab value by username key
                for k, v in r.items():
                    if k.lower() == "username" and isinstance(v, str):
                        email = v
                        break
            else:
                if r and isinstance(r[0], str):
                    email = r[0]
            if email is None:
                continue
            if not email.lower().endswith("@fastenal.com"):
                email = f"{email}@fastenal.com"
            emails.append((email,))
        rows = emails
        # prepare output
        out_base = general_cfg.get("output_dir")
        folder = group.output_path(out_base)
        os.makedirs(folder, exist_ok=True)
        # use date-only format YY-MM-DD
        date_str = datetime.now().strftime("%y-%m-%d")
        fname = f"{handle} ({group.display_name}) - {date_str}.csv"
        fullpath = os.path.join(folder, fname)
        # assume first row column names not available; no headers for simplicity
        tracker.update(handle, "writing CSV")
        executor.write_csv(rows, None, fullpath)
        tracker.update(handle, f"written {fullpath}")
        
        # send email if requested AND not using override email
        # (override emails are sent in bulk after all groups are processed)
        if should_email and not override_email:
            tracker.update(handle, "preparing email")
            email_method = general_cfg.get("email_method", "smtp")
            auto_send = general_cfg.get("outlook_auto_send", False)
            _email_report(
                group,
                general_cfg,
                fullpath,
                tracker,
                email_method=email_method,
                auto_send=auto_send,
                row_count=len(rows),
                date_str=date_str,
            )
        
        return fullpath
    except Exception as e:
        tracker.update(handle, f"failed: {e}")
        return None
    finally:
        tracker.increment(handle)


def _send_override_email(
    recipient: str,
    general_cfg: dict,
    csv_files: List[str],
    groups_list: str,
    date_str: str,
    count: int,
) -> bool:
    """Send all generated CSVs in a single email to an override recipient.
    
    Args:
        recipient: email address to send to
        general_cfg: general configuration dict
        csv_files: list of CSV file paths to attach
        groups_list: formatted string of group names (for template rendering)
        date_str: formatted date string
        count: number of groups/reports
        
    Returns:
        True if email sent successfully, False otherwise
    """
    from .email_util import send_email
    from .email_template import load_override_email_template, render_override_template
    from .outlook_util import send_via_outlook

    # load override template and render
    template = load_override_email_template()
    subject, body = render_override_template(
        template,
        groups_list=groups_list,
        date=date_str,
        count=count,
    )

    email_method = general_cfg.get("email_method", "smtp")
    
    # route to appropriate email method
    if email_method == "outlook":
        from .outlook_util import OUTLOOK_AVAILABLE
        if not OUTLOOK_AVAILABLE:
            print("Outlook integration not available; install pywin32 or use smtp.")
            return False
        # For Outlook, attach all CSV files
        auto_send = general_cfg.get("outlook_auto_send", False)
        # Note: send_via_outlook currently handles one attachment;
        # we'll need to send one email with all attachments
        success = True
        for csv_file in csv_files:
            s = send_via_outlook(
                recipient=recipient,
                subject=subject if csv_file == csv_files[0] else f"[Part {csv_files.index(csv_file) + 1}] {subject}",
                body=body if csv_file == csv_files[0] else "",
                csv_file=csv_file,
                auto_send=auto_send,
            )
            success = success and s
        return success
    else:
        # SMTP method - attach all CSVs in one email
        smtp_server = general_cfg.get("smtp_server")
        smtp_port = general_cfg.get("smtp_port", 25)
        smtp_from = general_cfg.get("smtp_from", "reports@fastenal.com")
        use_tls = general_cfg.get("smtp_use_tls", False)

        if not smtp_server:
            print("SMTP not configured; cannot send override email")
            return False

        # send one email with multiple attachments
        success = True
        for csv_file in csv_files:
            s = send_email(
                smtp_server=smtp_server,
                smtp_port=smtp_port,
                smtp_from=smtp_from,
                recipient=recipient,
                subject=subject,
                body=body if csv_file == csv_files[0] else f"(attachment {csv_files.index(csv_file) + 1})",
                csv_file=csv_file,
                use_tls=use_tls,
            )
            success = success and s
        return success


def _email_report(
    group: Group,
    general_cfg: dict,
    csv_file: str,
    tracker: ProgressTracker,
    email_method: str = "smtp",
    auto_send: bool = False,
    row_count: int = 0,
    date_str: str = "",
) -> None:
    """Email the generated CSV to configured recipients using SMTP or Outlook."""
    from .email_util import send_email
    from .email_template import load_email_template, render_template
    from .outlook_util import send_via_outlook

    # determine recipient: group config takes precedence over general config
    recipient = group.config.get("email_recipient") or general_cfg.get("email_recipient")
    if not recipient:
        tracker.update(group.handle, "email skipped (no recipient configured)")
        return

    # load email template and render with group context
    template = load_email_template()
    subject, body = render_template(
        template,
        group_name=group.display_name,
        group_handle=group.handle,
        date=date_str,
        count=row_count,
    )

    # route to appropriate email method
    if email_method == "outlook":
        from .outlook_util import OUTLOOK_AVAILABLE
        if not OUTLOOK_AVAILABLE:
            # give user guidance
            print("Outlook integration not available; install pywin32 or use smtp.")
            tracker.update(group.handle, "outlook unavailable - email not sent")
            return
        success = send_via_outlook(
            recipient=recipient,
            subject=subject,
            body=body,
            csv_file=csv_file,
            auto_send=auto_send,
        )
        if success:
            action = "sent" if auto_send else "prepared in Outlook"
            tracker.update(group.handle, f"email {action} to {recipient}")
        else:
            tracker.update(group.handle, f"failed to prepare Outlook email for {recipient}")
    else:
        # SMTP method
        smtp_server = general_cfg.get("smtp_server")
        smtp_port = general_cfg.get("smtp_port", 25)
        smtp_from = general_cfg.get("smtp_from", "reports@fastenal.com")
        use_tls = general_cfg.get("smtp_use_tls", False)

        if not smtp_server:
            tracker.update(group.handle, "email skipped (smtp_server not configured)")
            return

        success = send_email(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_from=smtp_from,
            recipient=recipient,
            subject=subject,
            body=body,
            csv_file=csv_file,
            use_tls=use_tls,
        )
        if success:
            tracker.update(group.handle, f"emailed to {recipient}")
        else:
            tracker.update(group.handle, f"failed to email {recipient}")


if __name__ == "__main__":
    main()
