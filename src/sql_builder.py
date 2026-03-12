"""SQL query builder for generating hierachical employee queries."""


def _extract_job_code(value: str) -> str:
    """Return job code from values like 'CODE - TITLE' (or raw code if no separator)."""
    if not value:
        return value
    if " - " in value:
        return value.split(" - ", 1)[0].strip()
    return value.strip()


def _normalize_persons(persons: list) -> list:
    """Normalize person payloads to list[{'person_id','person_username'}]."""
    if not isinstance(persons, list):
        return []

    normalized = []
    for person in persons:
        if isinstance(person, dict):
            pid = person.get("person_id") or person.get("id")
            username = person.get("person_username") or person.get("username")
            if isinstance(pid, str):
                pid = pid.strip()
            if isinstance(username, str):
                username = username.strip()
            if pid or username:
                normalized.append({
                    "person_id": pid,
                    "person_username": username,
                })
            continue

        if isinstance(person, str):
            raw = person.strip()
            if not raw:
                continue
            if raw.isdigit():
                normalized.append({"person_id": raw, "person_username": None})
            else:
                normalized.append({"person_id": None, "person_username": raw})

    return normalized

def generate_hierarchy_sql(
    mode: str,  # "by_person" or "by_role"/"by_attributes" or "all_employees"
    persons: list = None,  # list of {person_id, person_username} dicts
    additional_persons: list = None,  # optional explicit additions appended after main query
    root_people: list = None,  # optional list of {first_name,last_name,job_title} for root comment
    selected_person_details: list = None,  # ui-only, ignored by SQL generation
    additional_person_details: list = None,  # ui-only, ignored by SQL generation
    person_id: str = None,  # deprecated: single person
    person_first_name: str = None,
    person_last_name: str = None,
    person_username: str = None,  # deprecated: single person
    attributes_job_title: str = None,
    attributes_job_title_display: str = None,
    attributes_job_code: str = None,
    attributes_job_title_text: str = None,
    attributes_bu_code: str = None,
    attributes_company: str = None,
    attributes_tree_branch: str = None,
    attributes_department_id: str = None,
    filter_job_titles: list = None,
    filter_job_codes: list = None,
    filter_job_titles_display: list = None,
    filter_bu_codes: list = None,
    filter_companies: list = None,
    filter_tree_branches: list = None,
    filter_department_ids: list = None,
    filter_full_part_time: str = None,
    exclude_root: bool = False,
    direct_reports_only: bool = False,
) -> str:
    """
    Generate a hierarchy query. 
    
    mode: "by_person" (search by name/id), "by_attributes" (search by person attributes), or "all_employees" (entire population)
    persons: list of persons with id and username for multiple person queries
    Returns: SQL query string
    """
    
    if mode == "all_employees":
        # Simple query for all active employees, no hierarchy needed.
        filter_where_parts = []
        
        job_code_filters = filter_job_codes or ([_extract_job_code(jt) for jt in (filter_job_titles or [])] if filter_job_titles else [])
        if job_code_filters:
            job_codes_csv = ",".join([f"'{jc}'" for jc in job_code_filters])
            filter_where_parts.append(f"cte.JOB_CODE IN ({job_codes_csv})")
        
        if filter_bu_codes:
            bu_codes_csv = ",".join([f"'{bc}'" for bc in filter_bu_codes])
            filter_where_parts.append(f"cte.BU_CODE IN ({bu_codes_csv})")

        if filter_department_ids:
            department_ids_csv = ",".join([f"'{d}'" for d in filter_department_ids])
            filter_where_parts.append(f"cte.DEPARTMENT_ID IN ({department_ids_csv})")
        
        if filter_companies:
            companies_csv = ",".join([f"'{c}'" for c in filter_companies])
            filter_where_parts.append(f"cte.COMPANY IN ({companies_csv})")
        
        if filter_tree_branches:
            branches_csv = ",".join([f"'{tb}'" for tb in filter_tree_branches])
            filter_where_parts.append(f"cte.TREE_BRANCH IN ({branches_csv})")
        
        if filter_full_part_time:
            filter_where_parts.append(f"cte.FULL_PART_TIME = '{filter_full_part_time}'")

        where_clause = "\nWHERE cte.status_code != 'T'"
        if filter_where_parts:
            where_clause += "\n  AND " + "\n  AND ".join(filter_where_parts)

        final_query = f"""SELECT cte.USERNAME
FROM omsadm.employee_mv cte{where_clause}"""

        return final_query
    
    elif mode == "by_person":
        # Handle multiple persons or single person (backward compatibility)
        persons = _normalize_persons(persons)
        if not persons:
            if not person_id and not (person_first_name or person_last_name or person_username):
                raise ValueError("Must provide persons list or person_id/name/username for by_person mode")
            # Convert single person to persons format
            persons = [{"person_id": person_id, "person_username": person_username}]
        
        if not persons or len(persons) == 0:
            raise ValueError("Must provide at least one person for by_person mode")
        
        # Build queries for each person and UNION them  
        person_queries = []
        exclude_conditions = []
        
        for person in persons:
            pid = person.get('person_id')
            pusername = person.get('person_username')
            
            where_parts = ["status_code != 'T'"]
            
            if pusername:
                where_parts.append(f"AND USERNAME = '{pusername}'")
            elif pid:
                where_parts.append(f"AND EMPLOYEE_ID = '{pid}'")
            
            person_where = "\n".join(where_parts).replace("AND ", "", 1)
            
            if pusername:
                exclude_conditions.append(f"cte.USERNAME <> '{pusername}'")
            elif pid:
                exclude_conditions.append(f"cte.EMPLOYEE_ID <> '{pid}'")
        
        # Build the first person's query
        first_person = persons[0]
        first_pid = first_person.get('person_id')
        first_pusername = first_person.get('person_username')
        
        where_parts = ["status_code != 'T'"]
        if first_pusername:
            where_parts.append(f"AND USERNAME = '{first_pusername}'")
        elif first_pid:
            where_parts.append(f"AND EMPLOYEE_ID = '{first_pid}'")
        
        root_where = "\n".join(where_parts)
        
    elif mode in ("by_attributes", "by_role"):
        resolved_job_code = attributes_job_code or (attributes_job_title and _extract_job_code(attributes_job_title))
        if not (
            resolved_job_code
            or attributes_bu_code
            or attributes_company
            or attributes_tree_branch
            or attributes_department_id
        ):
            raise ValueError("Must provide at least one attribute for by_role mode")
        
        where_parts = ["status_code != 'T'"]
        
        if resolved_job_code:
            where_parts.append(f"AND JOB_CODE = '{resolved_job_code}'")
        if attributes_bu_code:
            where_parts.append(f"AND BU_CODE = '{attributes_bu_code}'")
        if attributes_company:
            where_parts.append(f"AND COMPANY = '{attributes_company}'")
        if attributes_tree_branch:
            where_parts.append(f"AND TREE_BRANCH = '{attributes_tree_branch}'")
        if attributes_department_id:
            where_parts.append(f"AND DEPARTMENT_ID = '{attributes_department_id}'")
        
        root_where = "\n".join(where_parts)
    else:
        raise ValueError("mode must be 'by_person', 'by_role' (or 'by_attributes'), or 'all_employees'")
    
    comment = ""
    additional_people = _normalize_persons(additional_persons)

    # Build the hierarchy using Oracle CONNECT BY syntax for each person
    hierarchy_parts = []
    
    if direct_reports_only:
        if mode == 'by_person' and persons and len(persons) > 1:
            for person in persons:
                pid = person.get('person_id')
                pusername = person.get('person_username')

                root_lookup = "status_code != 'T'"
                if pusername:
                    root_lookup += f" AND USERNAME = '{pusername}'"
                elif pid:
                    root_lookup += f" AND EMPLOYEE_ID = '{pid}'"

                hierarchy_parts.append(f"""SELECT EMPLOYEE_ID,
       USERNAME,
       JOB_CODE,
       DEPARTMENT_ID,
       BU_CODE,
       COMPANY,
       TREE_BRANCH,
       FULL_PART_TIME
FROM omsadm.employee_mv
WHERE status_code != 'T'
  AND SUPERVISOR_ID IN (
      SELECT EMPLOYEE_ID
      FROM omsadm.employee_mv
      WHERE {root_lookup}
  )""")
            hierarchy_sql = "\nUNION ALL\n".join(hierarchy_parts)
        else:
            hierarchy_sql = f"""SELECT EMPLOYEE_ID,
       USERNAME,
       JOB_CODE,
       DEPARTMENT_ID,
       BU_CODE,
       COMPANY,
       TREE_BRANCH,
       FULL_PART_TIME
FROM omsadm.employee_mv
WHERE status_code != 'T'
  AND SUPERVISOR_ID IN (
      SELECT EMPLOYEE_ID
      FROM omsadm.employee_mv
      WHERE {root_where}
  )"""
    elif mode == 'by_person' and persons and len(persons) > 1:
        # Multiple persons - build UNION query
        for person in persons:
            pid = person.get('person_id')
            pusername = person.get('person_username')
            
            person_where = "status_code != 'T'"
            if pusername:
                person_where += f" AND USERNAME = '{pusername}'"
            elif pid:
                person_where += f" AND EMPLOYEE_ID = '{pid}'"
            
            connect_by_exclude = ""
            if exclude_root:
                if pusername:
                    connect_by_exclude = f" AND USERNAME <> '{pusername}'"
                elif pid:
                    connect_by_exclude = f" AND EMPLOYEE_ID <> '{pid}'"
            
            hierarchy_parts.append(f"""SELECT EMPLOYEE_ID,
       USERNAME,
         JOB_CODE,
        DEPARTMENT_ID,
       BU_CODE,
       COMPANY,
       TREE_BRANCH,
       FULL_PART_TIME
FROM omsadm.employee_mv
START WITH {person_where}
CONNECT BY PRIOR EMPLOYEE_ID = SUPERVISOR_ID
AND status_code != 'T'{connect_by_exclude}""")
        
        hierarchy_sql = "\nUNION ALL\n".join(hierarchy_parts)
    else:
        # Single person or by_attributes
        hierarchy_sql = f"""SELECT EMPLOYEE_ID,
       USERNAME,
        JOB_CODE,
        DEPARTMENT_ID,
       BU_CODE,
       COMPANY,
       TREE_BRANCH,
       FULL_PART_TIME
FROM omsadm.employee_mv
    START WITH {root_where}
CONNECT BY PRIOR EMPLOYEE_ID = SUPERVISOR_ID
AND status_code != 'T'{f" AND USERNAME <> '{person_username}'" if mode=='by_person' and person_username else (f" AND EMPLOYEE_ID <> '{person_id}'" if mode=='by_person' and person_id else '')}"""
    
    # Build additional filters
    filter_where_parts = []
    
    job_code_filters = filter_job_codes or ([_extract_job_code(jt) for jt in (filter_job_titles or [])] if filter_job_titles else [])
    if job_code_filters:
        job_codes_csv = ",".join([f"'{jc}'" for jc in job_code_filters])
        filter_where_parts.append(f"cte.JOB_CODE IN ({job_codes_csv})")
    
    if filter_bu_codes:
        bu_codes_csv = ",".join([f"'{bc}'" for bc in filter_bu_codes])
        filter_where_parts.append(f"cte.BU_CODE IN ({bu_codes_csv})")

    if filter_department_ids:
        department_ids_csv = ",".join([f"'{d}'" for d in filter_department_ids])
        filter_where_parts.append(f"cte.DEPARTMENT_ID IN ({department_ids_csv})")
    
    if filter_companies:
        companies_csv = ",".join([f"'{c}'" for c in filter_companies])
        filter_where_parts.append(f"cte.COMPANY IN ({companies_csv})")
    
    if filter_tree_branches:
        branches_csv = ",".join([f"'{tb}'" for tb in filter_tree_branches])
        filter_where_parts.append(f"cte.TREE_BRANCH IN ({branches_csv})")
    
    if filter_full_part_time:
        filter_where_parts.append(f"cte.FULL_PART_TIME = '{filter_full_part_time}'")
    
    if exclude_root and not direct_reports_only and mode == "by_person" and persons and len(persons) == 1:
        # exclude root using whichever identifier was used for single person
        person = persons[0]
        if person.get('person_username'):
            filter_where_parts.append(f"cte.USERNAME <> '{person.get('person_username')}'")
        elif person.get('person_id'):
            filter_where_parts.append(f"cte.EMPLOYEE_ID <> '{person.get('person_id')}'")

    
    where_clause = ""
    if filter_where_parts:
        where_clause = "\nWHERE " + "\n  AND ".join(filter_where_parts)
    
    base_query = f"""SELECT cte.USERNAME
FROM ({hierarchy_sql}) cte{where_clause}"""

    if additional_people:
        addition_conditions = []
        for person in additional_people:
            if person.get("person_username"):
                addition_conditions.append(f"USERNAME = '{person.get('person_username')}'")
            elif person.get("person_id"):
                addition_conditions.append(f"EMPLOYEE_ID = '{person.get('person_id')}'")

        additions_query = f"""SELECT USERNAME
FROM omsadm.employee_mv
WHERE status_code != 'T'
  AND ({' OR '.join(addition_conditions)})"""

        final_query = f"""SELECT DISTINCT merged.USERNAME
FROM (
{base_query}
UNION
{additions_query}
) merged"""
    else:
        final_query = base_query
    
    return final_query


def _block_filters(block: dict) -> dict:
    """Extract normalized filter payload from a block."""
    filters = block.get("filters") if isinstance(block.get("filters"), dict) else {}

    job_titles_display = filters.get("job_titles_display")
    if not isinstance(job_titles_display, list) or not job_titles_display:
        job_titles_display = block.get("filter_job_titles_display") or []

    job_codes = filters.get("job_codes")
    if not isinstance(job_codes, list):
        job_codes = block.get("filter_job_codes") or []
    if not job_codes and job_titles_display:
        job_codes = [_extract_job_code(v) for v in job_titles_display if isinstance(v, str) and v.strip()]

    return {
        "filter_job_titles": job_titles_display,
        "filter_job_codes": job_codes,
        "filter_job_titles_display": job_titles_display,
        "filter_bu_codes": filters.get("bu_codes") if isinstance(filters.get("bu_codes"), list) else (block.get("filter_bu_codes") or []),
        "filter_companies": filters.get("companies") if isinstance(filters.get("companies"), list) else (block.get("filter_companies") or []),
        "filter_tree_branches": filters.get("tree_branches") if isinstance(filters.get("tree_branches"), list) else (block.get("filter_tree_branches") or []),
        "filter_department_ids": filters.get("department_ids") if isinstance(filters.get("department_ids"), list) else (block.get("filter_department_ids") or []),
        "filter_full_part_time": filters.get("full_part_time") or block.get("filter_full_part_time"),
    }


def _block_label(block_type: str) -> str:
    labels = {
        "hierarchy_by_person": "Hierarchy by person",
        "hierarchy_by_role": "Hierarchy by role",
        "filtered_population": "All employees with filters",
        "manual_individuals": "Manual individuals",
    }
    return labels.get(block_type, block_type or "Block")


def _manual_individuals_sql(persons: list) -> str:
    normalized = _normalize_persons(persons)
    if not normalized:
        return ""

    conditions = []
    for person in normalized:
        if person.get("person_username"):
            conditions.append(f"USERNAME = '{person.get('person_username')}'")
        elif person.get("person_id"):
            conditions.append(f"EMPLOYEE_ID = '{person.get('person_id')}'")

    if not conditions:
        return ""

    return f"""SELECT USERNAME
FROM omsadm.employee_mv
WHERE status_code != 'T'
  AND ({' OR '.join(conditions)})"""


def _block_to_sql(block: dict) -> str:
    block_type = block.get("type")
    if not block_type:
        raise ValueError("Each query block requires a type")

    filters = _block_filters(block)

    if block_type == "hierarchy_by_person":
        persons = block.get("persons") or block.get("selected_person_details") or []
        if not _normalize_persons(persons):
            return ""
        return generate_hierarchy_sql(
            mode="by_person",
            persons=persons,
            exclude_root=bool(block.get("exclude_root")),
            direct_reports_only=bool(block.get("direct_reports_only")),
            **filters,
        )

    if block_type == "hierarchy_by_role":
        attrs = block.get("attributes") if isinstance(block.get("attributes"), dict) else {}
        resolved_job_code = attrs.get("job_code") or block.get("attributes_job_code")
        resolved_job_title = attrs.get("job_title") or block.get("attributes_job_title")
        resolved_bu_code = attrs.get("bu_code") or block.get("attributes_bu_code")
        resolved_company = attrs.get("company") or block.get("attributes_company")
        resolved_tree_branch = attrs.get("tree_branch") or block.get("attributes_tree_branch")
        resolved_department_id = attrs.get("department_id") or block.get("attributes_department_id")

        if not (
            resolved_job_code
            or resolved_job_title
            or resolved_bu_code
            or resolved_company
            or resolved_tree_branch
            or resolved_department_id
        ):
            return ""

        return generate_hierarchy_sql(
            mode="by_role",
            attributes_job_title=resolved_job_title,
            attributes_job_title_display=attrs.get("job_title_display") or block.get("attributes_job_title_display"),
            attributes_job_code=resolved_job_code,
            attributes_job_title_text=attrs.get("job_title_text") or block.get("attributes_job_title_text"),
            attributes_bu_code=resolved_bu_code,
            attributes_company=resolved_company,
            attributes_tree_branch=resolved_tree_branch,
            attributes_department_id=resolved_department_id,
            direct_reports_only=bool(block.get("direct_reports_only")),
            **filters,
        )

    if block_type == "filtered_population":
        return generate_hierarchy_sql(
            mode="all_employees",
            **filters,
        )

    if block_type == "manual_individuals":
        people = block.get("persons") or block.get("selected_person_details") or []
        return _manual_individuals_sql(people)

    raise ValueError(f"Unsupported block type: {block_type}")


def generate_blocks_sql(blocks: list) -> str:
    """Generate SQL from ordered query blocks using UNION de-duplication."""
    if not isinstance(blocks, list) or len(blocks) == 0:
        raise ValueError("At least one block is required")

    preamble_comments = []
    parts = []
    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            raise ValueError("Each block must be an object")
        block_type = block.get("type")
        label = block.get("name") or _block_label(block_type)
        block_sql = _block_to_sql(block)
        if not block_sql or not str(block_sql).strip():
            preamble_comments.append(
                f"-- Block {index}: {label} (skipped: no qualifying selections)"
            )
            continue
        parts.append(f"-- Block {index}: {label}\n{block_sql}")

    if len(parts) == 0:
        comment_prefix = "\n".join(preamble_comments)
        if comment_prefix:
            comment_prefix += "\n"
        return f"{comment_prefix}SELECT USERNAME FROM omsadm.employee_mv WHERE 1=0"

    if len(parts) == 1:
        comment_prefix = "\n".join(preamble_comments)
        if comment_prefix:
            comment_prefix += "\n"
        return f"{comment_prefix}{parts[0]}"

    comment_prefix = "\n".join(preamble_comments)
    if comment_prefix:
        comment_prefix += "\n"
    return f"""SELECT DISTINCT merged.USERNAME
FROM (
{('\nUNION\n').join(parts)}
) merged""" if not comment_prefix else f"""{comment_prefix}SELECT DISTINCT merged.USERNAME
FROM (
{('\nUNION\n').join(parts)}
) merged"""


def generate_safe_hierarchy_sql(**kwargs) -> str:
    """
    Generate hierarchy SQL with basic injection prevention.
    Use this when values come from user input.
    """
    def sanitize(value):
        if isinstance(value, str):
            return value.replace("'", "''")
        if isinstance(value, list):
            return [sanitize(v) for v in value]
        if isinstance(value, dict):
            return {k: sanitize(v) for k, v in value.items()}
        return value

    # Basic sanitization: escape single quotes while preserving shapes
    kwargs = {key: sanitize(value) for key, value in kwargs.items()}

    if "blocks" in kwargs:
        return generate_blocks_sql(kwargs.get("blocks"))

    return generate_hierarchy_sql(**kwargs)
