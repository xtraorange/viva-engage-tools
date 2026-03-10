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
