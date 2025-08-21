import os
import re
from typing import Dict, Any, List, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# We import conditionally to keep offline mode light.
def _maybe_llm(model: str, temperature: float = 0.0):
    try:
        from langchain_openai import ChatOpenAI
        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            return None
        return ChatOpenAI(model=model, temperature=temperature)
    except Exception:
        return None

def naive_similarity(a: str, b: str) -> float:
    at = set(re.findall(r"[a-zA-Z0-9]+", a.lower()))
    bt = set(re.findall(r"[a-zA-Z0-9]+", b.lower()))
    if not at or not bt: 
        return 0.0
    return len(at & bt) / len(at | bt)

def pick_most_related(user_query: str, snippets: List[Dict[str, str]]) -> str:
    if not snippets:
        return ""
    best = max(snippets, key=lambda s: naive_similarity(user_query, s.get("sql","")))
    return best.get("sql", "")

def synthesize_sql(cfg: Dict[str, Any], user_query: str, schema: str, details: str, candidate_sql: str, table_name: str) -> str:
    """Return a SQL string. Uses LLM if configured; else offline rules."""
    if cfg["ai"]["offline_demo_mode"]:
        return offline_sql(user_query, table_name)
    llm = _maybe_llm(cfg["ai"]["model"], cfg["ai"]["temperature"])
    if llm is None:
        # fallback silently
        return offline_sql(user_query, table_name)

    prompt = ChatPromptTemplate.from_messages([
        ("system", cfg["ai"]["sql_synth_prompt"]),
        ("human",
         "User question:\n{user_query}\n\n"
         "DB schema:\n{schema}\n\n"
         "Additional details:\n{details}\n\n"
         "Most-related SQL (as a hint):\n{candidate_sql}\n\n"
         "Return ONLY a valid SQLite SQL query using the table named {table_name}.")
    ])
    chain = prompt | llm | StrOutputParser()
    sql = chain.invoke({
        "user_query": user_query,
        "schema": schema,
        "details": details,
        "candidate_sql": candidate_sql or "(none)",
        "table_name": table_name,
    })
    # sanitize: keep first semicolon, remove code fences
    sql = sql.strip().strip("`")
    if "```" in sql:
        sql = sql.split("```")[-2] if len(sql.split("```"))>=2 else sql
    # Ensure it's a single statement
    sql = sql.split(";")[0].strip() + ";"
    return sql

def offline_sql(user_query: str, table_name: str) -> str:
    """Very small rule-based translator for demo when no API key."""
    q = user_query.lower()

    # Count rows
    if "how many" in q or "count" in q:
        # optional column filter by equality if pattern like 'where item is X'
        m = re.search(r'\bitem\b\s*(?:=|is)\s*([A-Za-z0-9_ -]+)', q)
        if m:
            val = m.group(1).strip().strip('"\'')
            return f'SELECT COUNT(*) AS count FROM {table_name} WHERE item = "{val}";'
        return f"SELECT COUNT(*) AS count FROM {table_name};"

    # Sum revenue
    if "revenue" in q or "total sales" in q or "sum" in q:
        if "by item" in q or "per item" in q:
            return f'SELECT item, SUM(quantity*price) AS revenue FROM {table_name} GROUP BY item ORDER BY revenue DESC LIMIT 10;'
        if "by date" in q or "per day" in q or "daily" in q:
            return f'SELECT date, SUM(quantity*price) AS revenue FROM {table_name} GROUP BY date ORDER BY date;'
        return f"SELECT SUM(quantity*price) AS revenue FROM {table_name};"

    # Top-k items
    mtop = re.search(r"top\s+(\d+)", q)
    if mtop and ("item" in q or "product" in q):
        k = int(mtop.group(1))
        return f'SELECT item, SUM(quantity*price) AS revenue FROM {table_name} GROUP BY item ORDER BY revenue DESC LIMIT {k};'

    # Filter by customer or item if present
    m_cust = re.search(r'customer\s+(?:=|is|named)\s*([A-Za-z0-9_ -]+)', q)
    if m_cust:
        val = m_cust.group(1).strip().strip('"\'')
        return f'SELECT * FROM {table_name} WHERE customer = "{val}" LIMIT 50;'
    m_item = re.search(r'item\s+(?:=|is|named)\s*([A-Za-z0-9_ -]+)', q)
    if m_item:
        val = m_item.group(1).strip().strip('"\'')
        return f'SELECT * FROM {table_name} WHERE item = "{val}" LIMIT 50;'

    # default
    return f"SELECT * FROM {table_name} LIMIT 20;"

def answer_with_data(cfg: Dict[str, Any], user_query: str, sql: str, columns: List[str], rows: List[dict]) -> str:
    """Use LLM to craft a concise answer from rows; fallback to a textual summary."""
    if cfg["ai"]["offline_demo_mode"]:
        return offline_answer(user_query, sql, columns, rows)
    llm = _maybe_llm(cfg["ai"]["model"], cfg["ai"]["temperature"])
    if llm is None:
        return offline_answer(user_query, sql, columns, rows)

    system = cfg["ai"]["system_prompt"]
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human",
         "User question: {user_query}\n\n"
         "SQL used: {sql}\n\n"
         "Columns: {columns}\n\n"
         "Rows (JSON-like):\n{rows}\n\n"
         "Answer succinctly and include a 1-line takeaway.")
    ])
    chain = prompt | llm | StrOutputParser()
    # Limit rows rendered into prompt to avoid context blow-up
    head = rows[:50]
    return chain.invoke({
        "user_query": user_query,
        "sql": sql,
        "columns": columns,
        "rows": head,
    })

def offline_answer(user_query: str, sql: str, columns: List[str], rows: List[dict]) -> str:
    n = len(rows)
    if n == 0:
        return "I ran your query but found no matching rows."
    preview = rows[:5]
    # tiny summary heuristics
    if any("revenue" in c.lower() for c in columns) and n <= 10:
        # maybe report top 3
        parts = []
        for r in preview[:3]:
            if "item" in r and "revenue" in r:
                parts.append(f'{r["item"]}: {r["revenue"]}')
        if parts:
            return "Top results — " + "; ".join(parts)
    return f"Returned {n} rows. Showing first {min(5,n)} above."
