# -*- coding: utf-8 -*-
"""
audit_mariadb_sql.py – 프로젝트 전체 소스코드 MariaDB SQL 예약어 및 구문 전수 감사 & 자동 교정 도구
"""
import os
import sys
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXCLUDE_DIRS = {'.git', '__pycache__', '.venv', 'venv', 'docs', 'scratch', '.gemini'}
EXCLUDE_FILES = {'audit_mariadb_sql.py', 'db_writer_sqlite.py'}

def audit_file(filepath):
    rel_path = os.path.relpath(filepath, PROJECT_ROOT)
    # Skip sqlite repository files for sqlite-specific queries
    is_sqlite_repo = 'repositories\\sqlite' in rel_path or 'repositories/sqlite' in rel_path

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[!] Read failed {rel_path}: {e}")
        return 0, []

    changes = []
    new_content = content

    # 1. 예약어 key/value 백틱 이스케이프 교정 (SQL 구문 패턴 대상)
    replacements = [
        (r'(?i)\bWHERE\s+key\b(?!\s*`)', r'WHERE `key`'),
        (r'(?i)\bWHERE\s+value\b(?!\s*`)', r'WHERE `value`'),
        (r'(?i)\bSET\s+key\b(?!\s*`)', r'SET `key`'),
        (r'(?i)\bSET\s+value\b(?!\s*`)', r'SET `value`'),
        (r'(?i)\bSELECT\s+value\b(?!\s*`)', r'SELECT `value`'),
        (r'(?i)\bSELECT\s+key\b(?!\s*`)', r'SELECT `key`'),
        (r'(?i)\bSELECT\s+key\s*,\s*value\b', r'SELECT `key`, `value`'),
        (r'(?i)\bSELECT\s+`key`\s*,\s*value\b', r'SELECT `key`, `value`'),
        (r'(?i)\bSELECT\s+key\s*,\s*`value`\b', r'SELECT `key`, `value`'),
        (r'(?i)\bORDER\s+BY\s+key\b(?!\s*`)', r'ORDER BY `key`'),
        (r'(?i)\bGROUP\s+BY\s+key\b(?!\s*`)', r'GROUP BY `key`'),
        (r'(?i)\bON\s+settings\s*\(\s*key\b(?!\s*`)', r'ON settings (`key`'),
    ]

    for pattern, repl in replacements:
        def replace_fn(match):
            m_str = match.group(0)
            # Avoid replacing Python variable definitions like 'key =' or 'value =' if not SQL
            return repl

        # Only apply to SQL-like contexts (lines containing SELECT, UPDATE, DELETE, INSERT, WHERE, SET)
        lines = new_content.splitlines(keepends=True)
        modified_lines = []
        for line in lines:
            if any(k in line.upper() for k in ['SELECT', 'UPDATE', 'DELETE', 'INSERT', 'WHERE', 'SET', 'REPLACE', 'SETTINGS']):
                # Check if it's SQL string literal
                if re.search(r'["\'].*?(SELECT|UPDATE|DELETE|INSERT|WHERE|SET|SETTINGS).*?["\']', line, re.IGNORECASE):
                    new_line = re.sub(pattern, repl, line)
                    if new_line != line:
                        changes.append(f"  - Pattern '{pattern}' replaced in line: {line.strip()[:80]}")
                        line = new_line
            modified_lines.append(line)
        new_content = "".join(modified_lines)

    # 2. SQLite 전용 구문(INSERT OR IGNORE, INSERT OR REPLACE) 외부 모듈 경고/교정
    if not is_sqlite_repo and 'repositories/mariadb' not in rel_path and 'repositories\\mariadb' not in rel_path:
        if 'INSERT OR IGNORE' in new_content or 'INSERT OR REPLACE' in new_content:
            changes.append("  - Found SQLite-specific DML (INSERT OR IGNORE/REPLACE)")

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"[+] Modified ({len(changes)} changes): {rel_path}")
        for c in changes:
            print(c)
        return len(changes), changes
    return 0, []

def main():
    print("=" * 60)
    print(" BookOasis MariaDB SQL 예약어 및 구문 전수 감사 & 자동 교정 도구")
    print("=" * 60)

    total_files = 0
    modified_files = 0
    total_changes = 0

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if file.endswith('.py') and file not in EXCLUDE_FILES:
                total_files += 1
                filepath = os.path.join(root, file)
                count, _ = audit_file(filepath)
                if count > 0:
                    modified_files += 1
                    total_changes += count

    print("\n==================================================")
    print(f"✨ 전수 감사 결과: 총 {total_files}개 파이썬 파일 점검 완료.")
    print(f"   수정된 파일: {modified_files}개 파일 (총 {total_changes}개 구문 교정 완료)")
    print("==================================================")

if __name__ == '__main__':
    main()
