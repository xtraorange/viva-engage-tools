import pytest

from src.sql_builder import generate_hierarchy_sql, generate_safe_hierarchy_sql


def test_hierarchy_sql_contains_filter_columns():
    # ensure that the hierarchy query includes columns necessary for filters
    sql = generate_hierarchy_sql(
        mode="by_person",
        person_id="123",
        filter_job_titles=["mgr"],
        filter_bu_codes=["bu1"],
        filter_companies=["US"],
        filter_tree_branches=["A"],
    )
    # Root SELECT should include fields necessary for filters
    assert "BU_CODE" in sql
    assert "COMPANY" in sql
    assert "TREE_BRANCH" in sql
    # filters should reference the cte alias
    assert "cte.JOB_CODE" in sql
    assert "cte.BU_CODE" in sql


def test_hierarchy_sql_returns_only_username_column():
    sql = generate_hierarchy_sql(
        mode="by_person",
        person_id="123",
    )
    assert "SELECT cte.USERNAME" in sql
    assert "SELECT cte.*" not in sql


def test_generate_safe_hierarchy_sql_escapes_quotes():
    sql = generate_safe_hierarchy_sql(mode="by_person", person_username="o'brien")
    assert "o''brien" in sql


def test_attributes_mode_requires_at_least_one():
    with pytest.raises(ValueError):
        generate_hierarchy_sql(mode="by_role")


def test_by_role_mode_works_with_separated_job_code_fields():
    sql = generate_hierarchy_sql(
        mode="by_role",
        attributes_job_code="000545",
        attributes_job_title_text="Area Manager",
        attributes_department_id="02SA23",
        filter_job_codes=["000760"],
    )
    assert "JOB_CODE = '000545'" in sql
    assert "cte.JOB_CODE IN ('000760')" in sql
    assert "cte.USERNAME" in sql


def test_ignores_ui_only_selected_person_details_arg():
    sql = generate_safe_hierarchy_sql(
        mode="by_person",
        persons=[{"person_username": "gwilson"}],
        selected_person_details=[{"id": "1", "first_name": "Gary"}],
    )
    assert "gwilson" in sql


def test_by_person_accepts_string_person_entries():
    sql = generate_safe_hierarchy_sql(
        mode="by_person",
        persons=["gwilson"],
    )
    assert "USERNAME = 'gwilson'" in sql


def test_mode_specific_generation_ignores_other_mode_root_fields():
    sql = generate_safe_hierarchy_sql(
        mode="by_person",
        persons=[{"person_username": "gwilson"}],
        attributes_job_title="000123 - Some Title",
        attributes_bu_code="SHOULD_NOT_APPLY",
    )
    assert "USERNAME = 'gwilson'" in sql
    assert "SHOULD_NOT_APPLY" not in sql


def test_additional_people_are_unioned_after_main_query():
    sql = generate_safe_hierarchy_sql(
        mode="by_person",
        persons=[{"person_username": "gwilson"}],
        filter_bu_codes=["BU1"],
        additional_persons=[{"person_username": "extrauser"}],
    )
    assert "UNION" in sql
    assert "extrauser" in sql
    assert "cte.BU_CODE IN ('BU1')" in sql


def test_direct_reports_only_and_additional_people_can_coexist():
    sql = generate_safe_hierarchy_sql(
        mode="by_person",
        persons=[{"person_id": "12345"}],
        direct_reports_only=True,
        additional_persons=[{"person_id": "99999"}],
    )
    assert "SUPERVISOR_ID IN" in sql
    assert "99999" in sql


def test_block_builder_generation_unions_in_order_and_dedupes():
    sql = generate_safe_hierarchy_sql(
        blocks=[
            {
                "type": "manual_individuals",
                "name": "First",
                "persons": [{"person_username": "alice"}],
            },
            {
                "type": "manual_individuals",
                "name": "Second",
                "persons": [{"person_username": "bob"}],
            },
        ]
    )
    assert "-- Block 1: First" in sql
    assert "-- Block 2: Second" in sql
    assert "UNION" in sql
    assert "SELECT DISTINCT merged.USERNAME" in sql
    assert "alice" in sql
    assert "bob" in sql


def test_block_builder_role_block_with_filters():
    sql = generate_safe_hierarchy_sql(
        blocks=[
            {
                "type": "hierarchy_by_role",
                "attributes": {
                    "job_code": "000545",
                    "department_id": "02SA23",
                },
                "filters": {
                    "job_titles_display": ["000760 - Some Title"],
                    "bu_codes": ["BU1"],
                },
            }
        ]
    )
    assert "JOB_CODE = '000545'" in sql
    assert "DEPARTMENT_ID = '02SA23'" in sql
    assert "cte.JOB_CODE IN ('000760')" in sql
    assert "cte.BU_CODE IN ('BU1')" in sql


def test_block_builder_ignores_empty_manual_individuals_block():
    sql = generate_safe_hierarchy_sql(
        blocks=[
            {
                "type": "manual_individuals",
                "name": "Manual",
                "persons": [],
            },
            {
                "type": "hierarchy_by_role",
                "attributes": {"job_code": "000545"},
            },
        ]
    )
    assert "JOB_CODE = '000545'" in sql
    assert "Manual individuals block requires" not in sql


def test_block_builder_ignores_empty_hierarchy_by_person_block():
    sql = generate_safe_hierarchy_sql(
        blocks=[
            {
                "type": "hierarchy_by_person",
                "name": "By Person",
                "persons": [],
            },
            {
                "type": "hierarchy_by_role",
                "attributes": {"job_code": "000545"},
            },
        ]
    )
    assert "JOB_CODE = '000545'" in sql
    assert "-- Block 1: By Person (skipped: no qualifying selections)" in sql


def test_block_builder_ignores_empty_hierarchy_by_role_block():
    sql = generate_safe_hierarchy_sql(
        blocks=[
            {
                "type": "hierarchy_by_role",
                "name": "By Role",
                "attributes": {},
            },
            {
                "type": "manual_individuals",
                "name": "Manual",
                "persons": [{"person_username": "alice"}],
            },
        ]
    )
    assert "alice" in sql
    assert "-- Block 1: By Role (skipped: no qualifying selections)" in sql
