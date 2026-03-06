"""SQL query builder for generating hierachical employee queries."""

def generate_hierarchy_sql(
    mode: str,  # "by_person" or "by_attributes"
    person_id: str = None,
    person_first_name: str = None,
    person_last_name: str = None,
    person_username: str = None,
    attributes_job_title: str = None,
    attributes_bu_code: str = None,
    attributes_company: str = None,
    attributes_tree_branch: str = None,
    filter_job_titles: list = None,
    filter_bu_codes: list = None,
    filter_companies: list = None,
    filter_tree_branches: list = None,
    filter_full_part_time: str = None,
    exclude_root: bool = False,
) -> str:
    """
    Generate a hierarchy query. 
    
    mode: "by_person" (search by name/id) or "by_attributes" (search by person attributes)
    Returns: SQL query string
    """
    
    if mode == "by_person":
        if not person_id and not (person_first_name or person_last_name or person_username):
            raise ValueError("Must provide person_id or name/username for by_person mode")
        
        # Build the WHERE clause to find the root employee
        where_parts = ["status_code != 'T'"]
        
        if person_id:
            where_parts.append(f"AND EMPLOYEE_ID = '{person_id}'")
        elif person_username:
            where_parts.append(f"AND USERNAME = '{person_username}'")
        elif person_first_name and person_last_name:
            where_parts.append(f"AND FIRST_NAME = '{person_first_name}' AND LAST_NAME = '{person_last_name}'")
        elif person_first_name:
            where_parts.append(f"AND FIRST_NAME = '{person_first_name}'")
        elif person_last_name:
            where_parts.append(f"AND LAST_NAME = '{person_last_name}'")
        
        root_where = "\n".join(where_parts)
        
    elif mode == "by_attributes":
        if not (attributes_job_title or attributes_bu_code or attributes_company or attributes_tree_branch):
            raise ValueError("Must provide at least one attribute for by_attributes mode")
        
        where_parts = ["status_code != 'T'"]
        
        if attributes_job_title:
            where_parts.append(f"AND JOB_TITLE = '{attributes_job_title}'")
        if attributes_bu_code:
            where_parts.append(f"AND BU_CODE = '{attributes_bu_code}'")
        if attributes_company:
            where_parts.append(f"AND COMPANY = '{attributes_company}'")
        if attributes_tree_branch:
            where_parts.append(f"AND TREE_BRANCH = '{attributes_tree_branch}'")
        
        root_where = "\n".join(where_parts)
    else:
        raise ValueError("mode must be 'by_person' or 'by_attributes'")
    
    # Build the hierarchy CTE
    hierarchy_cte = f"""WITH cte AS (
  SELECT EMPLOYEE_ID, FIRST_NAME, LAST_NAME, USERNAME, EMPLOYEE_ID, SUPERVISORID, SUPERVISOR_NAME,
         DEPARTMENT, JOB_TITLE, JOB_CODE, BU_CODE, COMPANY, TREE_BRANCH, FULL_PART_TIME,
         HIRE_DT, LAST_HIRE_DT, status_code
  FROM omsadm.employee_mv e
  WHERE {root_where}
  UNION ALL
  SELECT e.EMPLOYEE_ID, e.FIRST_NAME, e.LAST_NAME, e.USERNAME, e.EMPLOYEE_ID, e.SUPERVISORID, e.SUPERVISOR_NAME,
         e.DEPARTMENT, e.JOB_TITLE, e.JOB_CODE, e.BU_CODE, e.COMPANY, e.TREE_BRANCH, e.FULL_PART_TIME,
         e.HIRE_DT, e.LAST_HIRE_DT, e.status_code
  FROM omsadm.employee_mv e
  INNER JOIN cte ON cte.EMPLOYEE_ID = e.SUPERVISORID
  WHERE status_code != 'T'{f" AND e.EMPLOYEE_ID <> '{person_id}'" if mode == 'by_person' and person_id else ''}
)"""
    
    # Build additional filters
    filter_where_parts = []
    
    if filter_job_titles:
        job_titles_csv = ",".join([f"'{jt}'" for jt in filter_job_titles])
        filter_where_parts.append(f"cte.JOB_TITLE IN ({job_titles_csv})")
    
    if filter_bu_codes:
        bu_codes_csv = ",".join([f"'{bc}'" for bc in filter_bu_codes])
        filter_where_parts.append(f"cte.BU_CODE IN ({bu_codes_csv})")
    
    if filter_companies:
        companies_csv = ",".join([f"'{c}'" for c in filter_companies])
        filter_where_parts.append(f"cte.COMPANY IN ({companies_csv})")
    
    if filter_tree_branches:
        branches_csv = ",".join([f"'{tb}'" for tb in filter_tree_branches])
        filter_where_parts.append(f"cte.TREE_BRANCH IN ({branches_csv})")
    
    if filter_full_part_time:
        filter_where_parts.append(f"cte.FULL_PART_TIME = '{filter_full_part_time}'")
    
    if exclude_root and mode == "by_person":
        if person_id:
            filter_where_parts.append(f"cte.EMPLOYEE_ID <> '{person_id}'")
    
    where_clause = ""
    if filter_where_parts:
        where_clause = "\nWHERE " + "\n  AND ".join(filter_where_parts)
    
    final_query = f"""{hierarchy_cte}
SELECT cte.*
FROM cte{where_clause}"""
    
    return final_query


def generate_safe_hierarchy_sql(**kwargs) -> str:
    """
    Generate hierarchy SQL with basic injection prevention.
    Use this when values come from user input.
    """
    # Basic sanitization: escape single quotes
    for key in kwargs:
        if isinstance(kwargs[key], str):
            kwargs[key] = kwargs[key].replace("'", "''")
        elif isinstance(kwargs[key], list):
            kwargs[key] = [str(v).replace("'", "''") for v in kwargs[key]]
    
    return generate_hierarchy_sql(**kwargs)
