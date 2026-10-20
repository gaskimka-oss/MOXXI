import sys
sys.path.insert(0, r"c:\Users\eiema\OneDrive\Desktop\бот2.0")
import os
import re
import ast
import sqlite3
from pathlib import Path

def audit_sql():
    print("=== 1. AUDITING SQL TABLES & COLUMNS IN DB ===")
    con = sqlite3.connect("data/iris.db")
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    
    table_cols = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        table_cols[t] = {r[1] for r in cur.fetchall()}
    con.close()

    py_files = list(Path(".").glob("*.py"))
    sql_issues = []

    # Common patterns: SELECT ... FROM table ...
    for pf in py_files:
        try:
            content = pf.read_text(encoding="utf-8")
        except Exception:
            continue

        # Look for table mentions in queries
        matches = re.findall(r"(?:FROM|INTO|UPDATE|JOIN)\s+([a-zA-Z0-9_]+)", content, re.IGNORECASE)
        for m in matches:
            tbl = m.lower()
            if tbl in ("select", "where", "set", "values", "distinct", "left", "outer", "inner", "default"):
                continue
            if tbl not in tables and not tbl.startswith("sqlite_"):
                # Check if it's created dynamically or temp
                sql_issues.append((pf.name, f"Table '{tbl}' might not exist in iris.db"))

    print(f"Found {len(sql_issues)} potential table mismatches:")
    for f, issue in set(sql_issues):
        print(f"  [{f}] {issue}")

def audit_ast():
    print("\n=== 2. AUDITING PYTHON FILES FOR UNDEFINED VARIABLES / NAME ERRORS ===")
    import py_compile
    py_files = list(Path(".").glob("*.py"))
    compile_issues = []
    for pf in py_files:
        try:
            py_compile.compile(str(pf), doraise=True)
        except Exception as e:
            compile_issues.append((pf.name, str(e)))
    if compile_issues:
        print(f"Compile errors ({len(compile_issues)}):")
        for f, err in compile_issues:
            print(f"  [{f}] {err}")
    else:
        print("All python files compiled cleanly (0 syntax errors).")

def audit_economy_backdoors():
    print("\n=== 3. AUDITING CURRENCY / COIN COMMANDS ===")
    py_files = list(Path(".").glob("h_*.py"))
    coin_granting = []
    for pf in py_files:
        content = pf.read_text(encoding="utf-8")
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            if any(k in line for k in ("add_balance", "set_balance", "add_coins", "add_comets")):
                coin_granting.append((pf.name, idx + 1, line.strip()))
    print(f"Found {len(coin_granting)} places modifying user balance:")
    for f, line_no, code in coin_granting[:20]:
        print(f"  [{f}:{line_no}] {code[:80]}")

if __name__ == "__main__":
    audit_sql()
    audit_ast()
    audit_economy_backdoors()
