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
    # Root SELECT should include all the additional fields
    assert "JOB_TITLE" in sql
    assert "BU_CODE" in sql
    assert "COMPANY" in sql
    assert "TREE_BRANCH" in sql
    # filters should reference the cte alias
    assert "cte.JOB_TITLE" in sql
    assert "cte.BU_CODE" in sql


def test_generate_safe_hierarchy_sql_escapes_quotes():
    sql = generate_safe_hierarchy_sql(mode="by_person", person_username="o'brien")
    assert "o''brien" in sql


def test_attributes_mode_requires_at_least_one():
    with pytest.raises(ValueError):
        generate_hierarchy_sql(mode="by_attributes")
