"""Main routes for the web interface."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file
import csv
import io
import json
import os
import threading
import time
import uuid

from ...services.config_service import ConfigService
from ...services.employee_lookup_service import EmployeeLookupService, EXPORTABLE_FIELDS
from ...services.group_service import GroupService
from ...services.report_service import ReportService
from ...services.stats_service import StatsService
from ...generate_reports import discover_groups

def init_main_routes(app, base_path: str):
    """Initialize main routes with dependencies."""
    main_bp = Blueprint('main', __name__)
    config_service = ConfigService(base_path)
    group_service = GroupService(base_path)
    stats_service = StatsService(base_path)

    def _build_match_input(headers, row_dict):
        lowered = {header.lower(): header for header in headers}
        first_key = next((lowered[key] for key in lowered if "first" in key and "name" in key), None)
        last_key = next((lowered[key] for key in lowered if "last" in key and "name" in key), None)
        full_key = next((lowered[key] for key in lowered if key in {"name", "full name", "employee name"}), None)

        if first_key and last_key:
            first_name = (row_dict.get(first_key) or "").strip()
            last_name = (row_dict.get(last_key) or "").strip()
            return {
                "display": " ".join(part for part in [first_name, last_name] if part).strip(),
                "first_name": first_name,
                "last_name": last_name,
            }

        if full_key:
            display = (row_dict.get(full_key) or "").strip()
            parts = [part for part in display.split() if part]
            return {
                "display": display,
                "first_name": parts[0] if len(parts) >= 2 else "",
                "last_name": parts[-1] if len(parts) >= 2 else "",
            }

        values = [str(row_dict.get(header) or "").strip() for header in headers]
        non_empty = [value for value in values if value]
        if len(headers) >= 2:
            first_name = values[0]
            last_name = values[1]
            return {
                "display": " ".join(part for part in [first_name, last_name] if part).strip(),
                "first_name": first_name,
                "last_name": last_name,
            }

        display = non_empty[0] if non_empty else ""
        parts = [part for part in display.split() if part]
        return {
            "display": display,
            "first_name": parts[0] if len(parts) >= 2 else "",
            "last_name": parts[-1] if len(parts) >= 2 else "",
        }

    def _parse_match_upload(upload):
        content = upload.read()
        if not content:
            return [], []

        text = content.decode("utf-8-sig")
        sample = text[:2048]
        has_header = csv.Sniffer().has_header(sample) if sample.strip() else True
        reader = list(csv.reader(io.StringIO(text)))
        if not reader:
            return [], []

        first_row = [cell.strip() for cell in reader[0]]
        known_headers = {
            "first_name", "firstname", "last_name", "lastname", "name", "full_name",
            "employee_name", "employee_id", "username", "email"
        }
        normalized_first_row = {value.lower().replace(" ", "_") for value in first_row if value}
        if normalized_first_row and normalized_first_row.intersection(known_headers):
            has_header = True

        if has_header:
            headers = [header.strip() or f"Column {index + 1}" for index, header in enumerate(reader[0])]
            data_rows = reader[1:]
        else:
            headers = [f"Column {index + 1}" for index in range(len(reader[0]))]
            data_rows = reader

        rows = []
        for raw_row in data_rows:
            if not any(str(cell).strip() for cell in raw_row):
                continue
            padded = raw_row + [""] * (len(headers) - len(raw_row))
            rows.append({header: padded[index] for index, header in enumerate(headers)})
        return headers, rows

    def _match_cache_key(name_parts):
        return (
            (name_parts.get("display") or "").strip().lower(),
            (name_parts.get("first_name") or "").strip().lower(),
            (name_parts.get("last_name") or "").strip().lower(),
        )

    def _get_adhoc_state_store():
        return app.config.setdefault("adhoc_match_state_store", {})

    def _prune_adhoc_state_store(max_entries: int = 20, max_age_seconds: int = 7200):
        store = _get_adhoc_state_store()
        now = time.time()
        stale_tokens = [
            token for token, payload in store.items()
            if (now - float(payload.get("created_at", 0))) > max_age_seconds
        ]
        for token in stale_tokens:
            store.pop(token, None)

        if len(store) > max_entries:
            ordered = sorted(store.items(), key=lambda item: float(item[1].get("created_at", 0)))
            overflow = len(store) - max_entries
            for token, _ in ordered[:overflow]:
                store.pop(token, None)

    def _save_adhoc_state(headers, rows):
        _prune_adhoc_state_store()
        token = uuid.uuid4().hex
        store = _get_adhoc_state_store()
        store[token] = {
            "created_at": time.time(),
            "headers": headers,
            "rows": rows,
        }
        _prune_adhoc_state_store()
        return token

    def _describe_match_method(row, selected_index, has_selected_match):
        if not has_selected_match:
            return "No Match Selected"

        initial_selected_index = row.get("selected_index") if isinstance(row.get("selected_index"), int) else None
        is_manual_selection = selected_index != initial_selected_index
        match_source = row.get("match_source") or ""

        if match_source == "exact":
            return "Exact Manual Match" if is_manual_selection else "Exact Match"
        if match_source == "fuzzy":
            return "Fuzzy Manual Match" if is_manual_selection else "Fuzzy Auto Match"
        return "Manual Match" if is_manual_selection else "Matched"

    @main_bp.route("/adhoc-match", methods=["GET", "POST"])
    def adhoc_match():
        """Upload a CSV of names, review matches, and export enriched data."""
        if request.method == "POST":
            upload = request.files.get("csv_file")
            search_mode = request.form.get("search_mode", "exact_then_fuzzy").strip().lower()
            if search_mode not in {"fuzzy_only", "exact_then_fuzzy", "exact_only"}:
                search_mode = "exact_then_fuzzy"
            if not upload or not upload.filename:
                return render_template(
                    "adhoc_match.html",
                    error="Choose a CSV file to upload.",
                    exportable_fields=EXPORTABLE_FIELDS,
                    search_mode=search_mode,
                )

            cfg = config_service.load_general_config()
            lookup_service = EmployeeLookupService(cfg.get("oracle_tns"))

            try:
                headers, uploaded_rows = _parse_match_upload(upload)
            except Exception as exc:
                return render_template(
                    "adhoc_match.html",
                    error=f"Unable to read CSV: {exc}",
                    exportable_fields=EXPORTABLE_FIELDS,
                    search_mode=search_mode,
                    lookup_stats=None,
                )

            lookup_started = time.perf_counter()
            prepared_rows = []
            unique_requests = {}
            for row_index, row_dict in enumerate(uploaded_rows):
                name_parts = _build_match_input(headers, row_dict)
                cache_key = _match_cache_key(name_parts)
                prepared_rows.append((row_index, row_dict, name_parts, cache_key))
                if cache_key[0] and cache_key not in unique_requests:
                    unique_requests[cache_key] = name_parts

            exact_pair_keys = {
                (
                    (name_parts.get("first_name") or "").strip().lower(),
                    (name_parts.get("last_name") or "").strip().lower(),
                )
                for name_parts in unique_requests.values()
                if (name_parts.get("first_name") or "").strip() and (name_parts.get("last_name") or "").strip()
            }

            exact_batch_queries = 0
            if search_mode in {"exact_then_fuzzy", "exact_only"}:
                exact_batch_queries = max(1, (len(exact_pair_keys) + 199) // 200) if exact_pair_keys else 0

            exact_resolved_keys = set()
            fuzzy_fallback_attempted = 0
            fuzzy_fallback_resolved = 0
            match_cache = {cache_key: [] for cache_key in unique_requests}
            match_sources = {cache_key: "none" for cache_key in unique_requests}
            try:
                if search_mode in {"exact_then_fuzzy", "exact_only"} and unique_requests and hasattr(lookup_service, "search_candidates_batch"):
                    match_cache.update(
                        lookup_service.search_candidates_batch(
                            [
                                {
                                    "query": name_parts.get("display"),
                                    "first_name": name_parts.get("first_name"),
                                    "last_name": name_parts.get("last_name"),
                                }
                                for name_parts in unique_requests.values()
                            ],
                            limit=10,
                        )
                    )
                    for cache_key in unique_requests:
                        if match_cache.get(cache_key):
                            exact_resolved_keys.add(cache_key)
                            match_sources[cache_key] = "exact"

                if search_mode in {"exact_then_fuzzy", "exact_only"} and unique_requests and not hasattr(lookup_service, "search_candidates_batch") and hasattr(lookup_service, "search_candidates_exact"):
                    for cache_key, name_parts in unique_requests.items():
                        match_cache[cache_key] = lookup_service.search_candidates_exact(
                            query=name_parts["display"],
                            first_name=name_parts["first_name"],
                            last_name=name_parts["last_name"],
                            limit=10,
                        )
                        if match_cache[cache_key]:
                            exact_resolved_keys.add(cache_key)
                            match_sources[cache_key] = "exact"

                for cache_key, name_parts in unique_requests.items():
                    if search_mode == "exact_only":
                        continue
                    if search_mode == "exact_then_fuzzy" and match_cache.get(cache_key):
                        continue
                    fuzzy_fallback_attempted += 1
                    match_cache[cache_key] = lookup_service.search_candidates(
                        query=name_parts["display"],
                        first_name=name_parts["first_name"],
                        last_name=name_parts["last_name"],
                        limit=10,
                    )
                    if match_cache[cache_key]:
                        fuzzy_fallback_resolved += 1
                        match_sources[cache_key] = "fuzzy"
            except Exception as exc:
                return render_template(
                    "adhoc_match.html",
                    error=f"Unable to search employee matches right now. Check the database/network connection and try again. Details: {exc}",
                    exportable_fields=EXPORTABLE_FIELDS,
                    headers=[],
                    match_results=[],
                    search_mode=search_mode,
                    lookup_stats=None,
                )

            results = []
            for row_index, row_dict, name_parts, cache_key in prepared_rows:
                matches = match_cache.get(cache_key, []) if cache_key[0] else []
                selected_index = 0 if len(matches) == 1 else None
                results.append({
                    "row_index": row_index,
                    "original": row_dict,
                    "source_name": name_parts["display"],
                    "matches": matches,
                    "selected_index": selected_index,
                    "match_source": match_sources.get(cache_key, "none") if cache_key[0] else "none",
                })

            exact_resolved = len(exact_resolved_keys)
            lookup_elapsed_ms = int((time.perf_counter() - lookup_started) * 1000)
            lookup_stats = {
                "search_mode": search_mode,
                "uploaded_rows": len(uploaded_rows),
                "unique_names": len(unique_requests),
                "exact_pairs": len(exact_pair_keys),
                "exact_batch_queries": exact_batch_queries,
                "exact_resolved": exact_resolved,
                "fuzzy_fallback_attempted": fuzzy_fallback_attempted,
                "fuzzy_fallback_resolved": fuzzy_fallback_resolved,
                "elapsed_ms": lookup_elapsed_ms,
            }
            state_token = _save_adhoc_state(headers, results)

            return render_template(
                "adhoc_match.html",
                headers=headers,
                match_results=results,
                exportable_fields=EXPORTABLE_FIELDS,
                updating=app.config.get("updating"),
                update_error=app.config.get("update_error"),
                search_mode=search_mode,
                lookup_stats=lookup_stats,
                state_token=state_token,
            )

        return render_template(
            "adhoc_match.html",
            exportable_fields=EXPORTABLE_FIELDS,
            headers=[],
            match_results=[],
            search_mode="exact_then_fuzzy",
            lookup_stats=None,
            state_token="",
        )

    @main_bp.route("/adhoc-match/download", methods=["POST"])
    def adhoc_match_download():
        """Export reviewed ad hoc match results as CSV."""
        state_token = request.form.get("state_token", "").strip()
        raw_overrides = request.form.get("selection_overrides_json", "")
        download_scope = request.form.get("download_scope", "all").strip().lower()
        if download_scope not in {"all", "matched", "needs_review"}:
            download_scope = "all"
        selected_fields = [field.strip() for field in request.form.get("selected_fields_csv", "").split(",") if field.strip() in EXPORTABLE_FIELDS]
        if not state_token:
            return redirect(url_for("main.adhoc_match"))

        state = _get_adhoc_state_store().get(state_token)
        if not state:
            return redirect(url_for("main.adhoc_match"))

        overrides = {}
        if raw_overrides:
            try:
                parsed = json.loads(raw_overrides)
                if isinstance(parsed, dict):
                    overrides = parsed
            except json.JSONDecodeError:
                overrides = {}

        headers = state.get("headers") or []
        rows = state.get("rows") or []
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Original Row #"] + headers + [EXPORTABLE_FIELDS[field] for field in selected_fields])

        def _export_row_values(row, selected_index, selected_candidate=None):
            original = row.get("original") or {}
            matches = row.get("matches") or []
            has_selected_match = isinstance(selected_index, int) and 0 <= selected_index < len(matches)
            selected = selected_candidate if selected_candidate is not None else (matches[selected_index] if has_selected_match else {})
            export_values = []
            for field in selected_fields:
                if field == "match_method":
                    if selected_candidate is not None:
                        export_values.append("Review Candidate")
                    else:
                        export_values.append(_describe_match_method(row, selected_index, has_selected_match))
                else:
                    export_values.append(selected.get(field, ""))
            row_number = int(row.get("row_index", 0)) + 1
            return [row_number] + [original.get(header, "") for header in headers] + export_values

        for row in rows:
            matches = row.get("matches") or []
            selected_index = row.get("selected_index")
            override_key = str(row.get("row_index"))
            if override_key in overrides:
                override_value = overrides.get(override_key)
                if isinstance(override_value, int):
                    selected_index = override_value
                elif isinstance(override_value, str) and override_value.isdigit():
                    selected_index = int(override_value)
                else:
                    selected_index = None

            has_selected_match = isinstance(selected_index, int) and 0 <= selected_index < len(matches)
            needs_review = not has_selected_match

            if download_scope == "matched" and not has_selected_match:
                continue
            if download_scope == "needs_review" and not needs_review:
                continue

            if download_scope == "needs_review" and needs_review and len(matches) > 1:
                for candidate in matches:
                    writer.writerow(_export_row_values(row, selected_index, selected_candidate=candidate))
                continue

            writer.writerow(_export_row_values(row, selected_index))

        buffer = io.BytesIO(output.getvalue().encode("utf-8-sig"))
        buffer.seek(0)
        return send_file(buffer, mimetype="text/csv", as_attachment=True, download_name="adhoc_name_matches.csv")

    @main_bp.route("/")
    def index():
        """Main dashboard showing analytics and statistics."""
        groups = group_service.discover_groups()
        cfg = config_service.load_general_config()
        stats_service.record_available_reports(len(groups))
        metrics = stats_service.dashboard_metrics()

        group_meta = [
            {
                "handle": g.handle,
                "tags": sorted(list(g.tags)) if g.tags else [],
            }
            for g in groups
        ]

        return render_template("generate.html", config=cfg, metrics=metrics, group_meta=group_meta,
                               updating=app.config.get("updating"),
                               update_error=app.config.get("update_error"))

    @main_bp.route("/generate", methods=["GET", "POST"])
    def generate():
        """Report generation form and submission handler."""
        if request.method == "POST":
            # Handle form submission
            if app.config.get("updating"):
                return "Update in progress, please wait and refresh after restart", 503

            groups = group_service.discover_groups()
            cfg = config_service.load_general_config()

            selected_handles = request.form.getlist("groups")
            selected = [g for g in groups if g.handle in selected_handles]

            tag_sel = request.form.getlist("tags")
            for t in tag_sel:
                for g in groups:
                    if t in g.tags and g not in selected:
                        selected.append(g)

            should_email = request.form.get("email") == "on"
            override = request.form.get("override_email") or None
            stats_service.record_run_started(
                selected_groups=selected,
                should_email=should_email,
                override_email=override,
                default_recipient=cfg.get("email_recipient"),
            )

            # Start processing in background
            tracker = start_jobs(app, selected, should_email, override)
            app.config["tracker"] = tracker

            return redirect(url_for("main.status"))
        
        # Handle GET - show form
        groups = group_service.discover_groups()
        cfg = config_service.load_general_config()

        # Get all tags for the UI, with per-tag group counts
        tag_counts = {}
        for g in groups:
            for tag in g.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        tags = sorted(tag_counts.keys())
        metrics = stats_service.dashboard_metrics()
        group_meta = [
            {
                "handle": g.handle,
                "display_name": g.display_name or g.handle,
                "tags": sorted(list(g.tags)) if g.tags else [],
            }
            for g in groups
        ]

        return render_template("report_generate.html", config=cfg, groups=groups, tags=tags, tag_counts=tag_counts, metrics=metrics, group_meta=group_meta,
                               updating=app.config.get("updating"),
                               update_error=app.config.get("update_error"))

    @main_bp.route("/status")
    def status():
        """Show processing status."""
        tracker = app.config.get("tracker")
        if not tracker:
            return redirect(url_for("main.index"))

        return render_template("status.html", tracker=tracker)

    @main_bp.route("/api/status")
    def api_status():
        """API endpoint for status polling."""
        tracker = app.config.get("tracker")
        if not tracker:
            return jsonify(error="No job running")

        return jsonify(
            status=tracker.status,
            done=tracker.done,
            total=tracker.total,
            results=tracker.results
        )

    @main_bp.route("/settings", methods=["GET", "POST"])
    def settings():
        """Settings page."""
        cfg = config_service.load_general_config()
        metrics = stats_service.dashboard_metrics()

        if request.method == "POST":
            if request.form.get("reset_stats") == "1":
                stats_service.reset_stats()
                return redirect(url_for("main.settings"))

            # Update general config based on form fields
            for key in [
                "oracle_tns",
                "ui_port",
                "output_dir",
                "max_workers",
                "email_method",
                "outlook_auto_send",
                "smtp_server",
                "smtp_port",
                "smtp_use_tls",
                "smtp_from",
                "email_recipient",
            ]:
                if key in request.form:
                    val = request.form.get(key)
                    if val == "":
                        cfg.pop(key, None)
                    else:
                        if key in ["ui_port", "max_workers", "smtp_port"]:
                            try:
                                cfg[key] = int(val)
                            except ValueError:
                                cfg[key] = val
                        elif key in ["smtp_use_tls", "outlook_auto_send"]:
                            cfg[key] = request.form.get(key) == "on"
                        else:
                            cfg[key] = val

            config_service.save_general_config(cfg)
            return redirect(url_for("main.settings"))

        groups = group_service.discover_groups()
        return render_template("settings.html", config=cfg, groups=groups, metrics=metrics,
                               updating=app.config.get("updating"),
                               update_error=app.config.get("update_error"))

    @main_bp.route("/api/dashboard-stats")
    def dashboard_stats():
        """Return dashboard metrics for chart rendering."""
        return jsonify(stats_service.dashboard_metrics())

    return main_bp


def start_jobs(app, selected, should_email, override_email):
    """Start background job processing."""
    from ...services.config_service import ConfigService
    from ...services.report_service import ReportService

    base = os.getcwd()
    config_service = ConfigService(base)
    cfg = config_service.load_general_config()
    report_service = ReportService(cfg)
    stats_service = StatsService(base)

    # create tracker that will be visible to the UI
    from ...db import ProgressTracker
    tracker = ProgressTracker(len(selected))

    def task():
        started = time.perf_counter()
        # pass the tracker so it gets updated during processing
        generated = report_service.process_groups(
            selected,
            should_email,
            override_email,
            tracker=tracker,
            return_details=True,
        )
        stats_service.record_run_completed(
            selected_handles=[g.handle for g in selected],
            generated_files=generated.get("csv_files", []),
            duration_seconds=time.perf_counter() - started,
            group_run_details=generated.get("group_run_details", {}),
        )
        # Processing complete - tracker will be cleaned up by the UI

    threading.Thread(target=task, daemon=True).start()

    # Return the tracker for status monitoring
    return tracker