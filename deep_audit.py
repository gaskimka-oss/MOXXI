import ast
import builtins
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"c:\Users\eiema\OneDrive\Desktop\бот2.0")
sys.path.insert(0, str(ROOT))

BUILTIN_NAMES = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__"}

def audit_undefined_names():
    print("=== CHECKING FOR UNDEFINED VARIABLES IN FUNCTIONS ===")
    issues = []
    
    # Analyze each h_*.py file
    for p in ROOT.glob("h_*.py"):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"), filename=p.name)
        except Exception as e:
            issues.append((p.name, 0, f"Parse error: {e}"))
            continue

        global_scope = set(BUILTIN_NAMES)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                global_scope.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        global_scope.add(target.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    global_scope.add(alias.asname or alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    global_scope.add(alias.asname or alias.name)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_scope = set(global_scope)
                # add arguments
                for arg in node.args.args:
                    local_scope.add(arg.arg)
                for arg in node.args.kwonlyargs:
                    local_scope.add(arg.arg)
                if node.args.vararg:
                    local_scope.add(node.args.vararg.arg)
                if node.args.kwarg:
                    local_scope.add(node.args.kwarg.arg)

                # Collect all local assignments and imports inside function
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Assign):
                        for target in inner.targets:
                            if isinstance(target, ast.Name):
                                local_scope.add(target.id)
                            elif isinstance(target, (ast.Tuple, ast.List)):
                                for elt in target.elts:
                                    if isinstance(elt, ast.Name):
                                        local_scope.add(elt.id)
                    elif isinstance(inner, (ast.For, ast.AsyncFor)):
                        if isinstance(inner.target, ast.Name):
                            local_scope.add(inner.target.id)
                        elif isinstance(inner.target, (ast.Tuple, ast.List)):
                            for elt in inner.target.elts:
                                if isinstance(elt, ast.Name):
                                    local_scope.add(elt.id)
                    elif isinstance(inner, (ast.With, ast.AsyncWith)):
                        for item in inner.items:
                            if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                                local_scope.add(item.optional_vars.id)
                    elif isinstance(inner, ast.Import):
                        for alias in inner.names:
                            local_scope.add(alias.asname or alias.name.split('.')[0])
                    elif isinstance(inner, ast.ImportFrom):
                        for alias in inner.names:
                            local_scope.add(alias.asname or alias.name)
                    elif isinstance(inner, ast.ExceptHandler):
                        if inner.name:
                            local_scope.add(inner.name)

                # Now check loaded names in this function
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Name) and isinstance(inner.ctx, ast.Load):
                        if inner.id not in local_scope:
                            # Filter out known dynamic or forward-ref names
                            if inner.id not in ("Exception", "True", "False", "None"):
                                issues.append((p.name, inner.lineno, f"'{inner.id}' may be undefined in '{node.name}'"))

    print(f"Total potential NameError issues: {len(issues)}")
    for f, line, msg in issues[:30]:
        print(f"  [{f}:{line}] {msg}")

def audit_sql_schema():
    print("\n=== CHECKING SQL QUERIES AGAINST DB SCHEMA ===")
    con = sqlite3.connect(ROOT / "data" / "iris.db")
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    
    table_cols = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        table_cols[t] = {r[1] for r in cur.fetchall()}
    con.close()

    sql_errors = []
    for p in ROOT.glob("h_*.py"):
        text = p.read_text(encoding="utf-8")
        # Find raw SQL queries
        queries = re.findall(r'(?:execute|fetchone|fetchall)\(\s*["\']([^"\']+)["\']', text)
        for q in queries:
            q_clean = q.strip().replace("\n", " ")
            m_select = re.search(r'SELECT\s+(.*?)\s+FROM\s+([a-zA-Z0-9_]+)', q_clean, re.IGNORECASE)
            if m_select:
                cols_part = m_select.group(1).strip()
                tbl = m_select.group(2).strip().lower()
                if tbl in tables:
                    # check cols
                    if cols_part != "*" and "COUNT(" not in cols_part.upper():
                        # Parse simple comma separated cols
                        for col_item in cols_part.split(","):
                            col_clean = col_item.strip().split()[-1].split(".")[-1]
                            col_clean = col_clean.replace("(", "").replace(")", "")
                            if col_clean and not col_clean.isdigit() and col_clean.lower() not in ("distinct", "*", "as"):
                                if col_clean not in table_cols[tbl]:
                                    sql_errors.append((p.name, f"Query '{q_clean[:60]}' references unknown column '{col_clean}' in table '{tbl}'"))
                else:
                    if not tbl.startswith("sqlite_"):
                        sql_errors.append((p.name, f"Query '{q_clean[:60]}' references unknown table '{tbl}'"))

    print(f"Total SQL schema issues: {len(sql_errors)}")
    for f, msg in set(sql_errors):
        print(f"  [{f}] {msg}")

if __name__ == "__main__":
    audit_undefined_names()
    audit_sql_schema()
