"""
Read-only tools for the agent. Parameterized SELECT only, no raw SQL from LLM.
"""
import json
import decimal
import datetime
import calendar
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from langchain_core.tools import tool

from database import get_conn, assert_table_allowed

TABLE = "projects"


def _json_safe(value):
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return str(value) if hasattr(value, "hex") else value  # UUID -> str


def _row_to_dict(row: dict) -> dict:
    return {k: _json_safe(v) for k, v in row.items()}


def _run_query(where_sql: str, params: dict, limit: int) -> List[Dict[str, Any]]:
    assert_table_allowed(TABLE)
    sql = f"""
        SELECT p.id, p.name, p.status, p.deadline, p.assigned_to,
               m.name AS assigned_to_name,
               p.budget, p.created_at, p.is_deleted, p.description
        FROM {TABLE} p
        LEFT JOIN team_members m ON m.id = p.assigned_to
        WHERE p.is_deleted = false {where_sql}
        ORDER BY p.created_at DESC
        LIMIT :limit
    """
    params["limit"] = limit
    with get_conn() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
        return [_row_to_dict(dict(r)) for r in rows]


@tool
def query_projects(
    search: Optional[str] = None,
    status: Optional[str] = None,
    member_id: Optional[str] = None,
    member_name: Optional[str] = None,
    deadline_month: Optional[str] = None,
    budget_min: Optional[float] = None,
    budget_max: Optional[float] = None,
    limit: int = 200,
) -> str:
    """
    Fetch project data from Supabase with optional filters. Use this tool
    whenever the user asks for project data/list/report.

    Args:
        search: search by project name (partial match, case-insensitive).
        status: filter by project status, e.g. 'active', 'completed', 'on hold'.
        member_id: filter by assigned member's UUID (assigned_to), if available.
        member_name: filter by assigned member's name (partial match, case-insensitive). Use this when the user mentions a person's name instead of a UUID.
        deadline_month: filter by deadline month, format YYYY-MM (e.g. '2026-11').
        budget_min: minimum budget filter (number).
        budget_max: maximum budget filter (number).
        limit: max rows to return (default 200, max 1000).

    Returns:
        JSON string containing the list of project data matching the filters, newest first.
    """
    limit = min(max(int(limit), 1), 1000)
    where = []
    params: dict = {}

    if search:
        where.append("AND p.name ILIKE :search")
        params["search"] = f"%{search}%"
    if status:
        where.append("AND REPLACE(p.status, '_', ' ') ILIKE :status")
        params["status"] = status.replace("_", " ")
    if member_id:
        where.append("AND p.assigned_to = :member_id")
        params["member_id"] = member_id
    if member_name:
        where.append("AND m.name ILIKE :member_name")
        params["member_name"] = f"%{member_name}%"
    if deadline_month:
        try:
            year, month = map(int, deadline_month.split("-"))
            last_day = calendar.monthrange(year, month)[1]
            params["deadline_from"] = f"{year:04d}-{month:02d}-01"
            params["deadline_to"] = f"{year:04d}-{month:02d}-{last_day:02d}"
            where.append("AND p.deadline >= :deadline_from AND p.deadline <= :deadline_to")
        except ValueError:
            pass
    if budget_min is not None:
        where.append("AND p.budget >= :budget_min")
        params["budget_min"] = budget_min
    if budget_max is not None:
        where.append("AND p.budget <= :budget_max")
        params["budget_max"] = budget_max

    rows = _run_query(" ".join(where), params, limit)
    return json.dumps(rows, ensure_ascii=False)


TOOLS = [query_projects]