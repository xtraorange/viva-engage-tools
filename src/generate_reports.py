import argparse
import os
import sys
from typing import List

from .services.config_service import ConfigService
from .services.group_service import GroupService
from .services.report_service import ReportService
from .group import Group
from . import email_util, outlook_util


def _email_report(group, general_cfg, csv_file, tracker, email_method=None):
    """Backward-compatible email helper used by older tests/integrations."""
    method = email_method or general_cfg.get("email_method", "smtp")
    recipient = group.config.get("email_recipient") or general_cfg.get("email_recipient")

    if not recipient:
        tracker.update(group.handle, "skipped: no email recipient configured")
        return False

    subject = f"Viva Engage members - {group.display_name}"
    body = f"Attached is the latest member list for {group.display_name}."

    if method == "outlook":
        if not outlook_util.OUTLOOK_AVAILABLE:
            tracker.update(group.handle, "outlook unavailable")
            return False
        ok = outlook_util.send_via_outlook(
            recipient=recipient,
            subject=subject,
            body=body,
            csv_file=csv_file,
            auto_send=general_cfg.get("outlook_auto_send", False),
        )
    else:
        ok = email_util.send_email(
            smtp_server=general_cfg.get("smtp_server"),
            smtp_port=general_cfg.get("smtp_port", 25),
            smtp_from=general_cfg.get("smtp_from", "reports@fastenal.com"),
            recipient=recipient,
            subject=subject,
            body=body,
            csv_file=csv_file,
            use_tls=general_cfg.get("smtp_use_tls", False),
        )

    tracker.update(group.handle, "emailed" if ok else "email failed")
    return ok


def discover_groups(base_path: str) -> List[Group]:
    """Discover all groups in the groups directory."""
    group_service = GroupService(base_path)
    return group_service.discover_groups()


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


def process_group(
    group: Group,
    config: dict,
    executor,
    tracker,
    should_email: bool = False,
    job_num: int = 1,
    job_total: int = 1,
):
    """Backward-compatible wrapper used by tests and older integrations."""
    service = ReportService(config)
    return service._process_single_group(
        group=group,
        executor=executor,
        tracker=tracker,
        should_email=should_email,
        override_email=None,
        job_num=job_num,
        job_total=job_total,
    )


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
    parser.add_argument(
        "--cli",
        action="store_true",
        help="run in command-line interface mode",
    )
    args = parser.parse_args()

    base = os.getcwd()
    # Keep backward compatibility for CLI usage like: `python run_reports.py list`
    # and only launch the web UI when no actionable CLI args are present.
    should_launch_web = (not args.cli) and (not args.names) and (args.email is None)
    if should_launch_web:
        from .ui import run_app
        run_app()
        return

    # CLI mode
    config_service = ConfigService(base)
    group_service = GroupService(base)
    report_service = ReportService(config_service.load_general_config())

    groups = group_service.discover_groups()

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

    # Process the groups using the report service
    csv_files = report_service.process_groups(selected, should_email, override_email)

    print("All done.")
