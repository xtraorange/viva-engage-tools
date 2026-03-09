"""SQL query builder for generating hierachical employee queries."""

def generate_hierarchy_sql(
    mode: str,  # "by_person" or "by_attributes" or "all_employees"
    persons: list = None,  # list of {person_id, person_username} dicts
    person_id: str = None,  # deprecated: single person
    person_first_name: str = None,
    person_last_name: str = None,
    person_username: str = None,  # deprecated: single person
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
    
    mode: "by_person" (search by name/id), "by_attributes" (search by person attributes), or "all_employees" (entire population)
    persons: list of persons with id and username for multiple person queries
    Returns: SQL query string
    """
    
    if mode == "all_employees":
        # Simple query for all active employees, no hierarchy needed
        base_sql = """SELECT EMPLOYEE_ID,
       USERNAME,
       JOB_TITLE,
       BU_CODE,
       COMPANY,
       TREE_BRANCH,
       FULL_PART_TIME
FROM omsadm.employee_mv
WHERE status_code != 'T'"""
        
        # Build filters
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
        
        where_clause = ""
        if filter_where_parts:
            where_clause = "\nWHERE " + "\n  AND ".join(filter_where_parts)
        
        final_query = f"""SELECT cte.*
FROM ({base_sql}) cte{where_clause}"""
        
        return final_query
    
    elif mode == "by_person":
        # Handle multiple persons or single person (backward compatibility)
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
        raise ValueError("mode must be 'by_person', 'by_attributes', or 'all_employees'")
    
    # Build a friendly comment indicating the root employee(s) (if known)
    comment = ''
    if mode == 'by_person' and persons:
        person_strs = []
        for person in persons:
            if person.get('person_username'):
                person_strs.append(f"username={person.get('person_username')}")
            elif person.get('person_id'):
                person_strs.append(f"id={person.get('person_id')}")
        if person_strs:
            comment = "-- hierarchy roots: " + " / ".join(person_strs) + "\n"

    # Build the hierarchy using Oracle CONNECT BY syntax for each person
    hierarchy_parts = []
    
    if mode == 'by_person' and persons and len(persons) > 1:
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
       JOB_TITLE,
       BU_CODE,
       COMPANY,
       TREE_BRANCH,
       FULL_PART_TIME
FROM omsadm.employee_mv
START WITH {person_where}
CONNECT BY PRIOR EMPLOYEE_ID = SUPERVISOR_ID
AND status_code != 'T'{connect_by_exclude}""")
        
        hierarchy_sql = comment + "\nUNION ALL\n".join(hierarchy_parts)
    else:
        # Single person or by_attributes
        hierarchy_sql = comment + f"""SELECT EMPLOYEE_ID,
       USERNAME,
       JOB_TITLE,
       BU_CODE,
       COMPANY,
       TREE_BRANCH,
       FULL_PART_TIME
FROM omsadm.employee_mv
START WITH {root_where.replace("status_code != 'T' AND ", "").replace("status_code != 'T'", "1=1")}
CONNECT BY PRIOR EMPLOYEE_ID = SUPERVISOR_ID
AND status_code != 'T'{f" AND USERNAME <> '{person_username}'" if mode=='by_person' and person_username else (f" AND EMPLOYEE_ID <> '{person_id}'" if mode=='by_person' and person_id else '')}"""
    
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
    
    if exclude_root and mode == "by_person" and persons and len(persons) == 1:
        # exclude root using whichever identifier was used for single person
        person = persons[0]
        if person.get('person_username'):
            filter_where_parts.append(f"cte.USERNAME <> '{person.get('person_username')}'")
        elif person.get('person_id'):
            filter_where_parts.append(f"cte.EMPLOYEE_ID <> '{person.get('person_id')}'")

    
    where_clause = ""
    if filter_where_parts:
        where_clause = "\nWHERE " + "\n  AND ".join(filter_where_parts)
    
    final_query = f"""SELECT cte.*
FROM ({hierarchy_sql}) cte{where_clause}"""
    
    return final_query


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
    
    return generate_hierarchy_sql(**kwargs)
