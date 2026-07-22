# -*- coding: utf-8 -*-
"""
db_recovery.py - BookOasis DB 임시 복구 스크립트
=================================================
사용 목적:
  "database disk image is malformed" 에러 발생 시
  WAL 파일 정리 및 DB 무결성 복구를 시도합니다.

사용 방법:
  1. 먼저 BookOasis 서버(컨테이너)를 완전히 정지하세요.
     $ docker stop bookoasis

  2. 이 스크립트를 media_server 루트 디렉토리에서 실행하세요.
     $ python tools/db_recovery.py

  3. 복구 완료 후 서버를 재시작하세요.
     $ docker start bookoasis
"""

import os
import sys
import shutil
import sqlite3
import datetime
import subprocess
import argparse
import re

# ─────────────────────────────────────────────
# 경로 설정 (이 스크립트 위치 기준으로 자동 탐색)
# ─────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.dirname(SCRIPT_DIR)          # media_server 루트
DB_DIR      = os.path.join(BASE_DIR, 'db')
BACKUP_DIR  = os.path.join(BASE_DIR, 'db', '_backup')

DB_FILES = {
    'general': os.path.join(DB_DIR, 'media_general.db'),
    'adult'  : os.path.join(DB_DIR, 'media_adult.db'),
}

# ─────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────
def sep(char='─', width=60):
    print(char * width)

def log(msg, prefix='  '):
    print(f"{prefix}{msg}")

def timestamp():
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

# ─────────────────────────────────────────────
# STEP 1: WAL 체크포인트 (데이터 손실 없음)
# ─────────────────────────────────────────────
def step1_wal_checkpoint(db_path, label):
    """WAL/SHM 파일을 메인 DB에 병합 후 정리합니다."""
    sep()
    log(f"[{label}] WAL 체크포인트 시작", prefix='')

    if not os.path.exists(db_path):
        log("⚠️  DB 파일이 존재하지 않습니다. 건너뜁니다.")
        return False

    wal_path = db_path + '-wal'
    shm_path = db_path + '-shm'
    has_wal  = os.path.exists(wal_path)
    has_shm  = os.path.exists(shm_path)

    log(f"경로: {db_path}")
    log(f"WAL 파일: {'✅ 존재 (' + str(os.path.getsize(wal_path)) + ' bytes)' if has_wal else '없음'}")
    log(f"SHM 파일: {'✅ 존재' if has_shm else '없음'}")

    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")

        # 무결성 사전 체크
        log("무결성 체크 중...")
        result = conn.execute("PRAGMA integrity_check;").fetchall()
        integrity_ok = (len(result) == 1 and result[0][0] == 'ok')
        if integrity_ok:
            log("✅ integrity_check: OK")
        else:
            log(f"❌ integrity_check 이상 감지: {result[:3]}")
            conn.close()
            return False

        # WAL 체크포인트 강제 수행
        log("WAL 체크포인트(TRUNCATE) 실행 중...")
        ckpt = conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
        log(f"결과: busy={ckpt[0]}, log={ckpt[1]}, checkpointed={ckpt[2]}")
        conn.close()

        # WAL/SHM 파일이 남아있으면 강제 제거
        for extra in [wal_path, shm_path]:
            if os.path.exists(extra):
                os.remove(extra)
                log(f"임시 파일 제거: {os.path.basename(extra)}")

        log(f"✅ [{label}] WAL 체크포인트 완료 — 데이터 손실 없음")
        return True

    except sqlite3.DatabaseError as e:
        log(f"❌ DB 에러: {e}")
        log("→ DB 자체가 손상되었을 수 있습니다. Step 2(전체 복구)를 시도하세요.")
        return False
    except Exception as e:
        log(f"❌ 예기치 못한 오류: {e}")
        return False

# ─────────────────────────────────────────────
# STEP 2: 전체 복구 (.recover 덤프 재생성)
# ─────────────────────────────────────────────
def step2_full_recovery(db_path, label):
    """
    DB 파일이 실제로 손상된 경우 .recover 명령으로 데이터를 추출하여
    새 DB를 생성합니다. 최근 일부 변경사항은 손실될 수 있습니다.
    """
    sep()
    log(f"[{label}] 전체 복구 시작 (STEP 2)", prefix='')
    log("⚠️  주의: 이 작업은 DB를 재생성합니다. 최근 일부 변경사항이 손실될 수 있습니다.")

    if not os.path.exists(db_path):
        log("⚠️  DB 파일이 존재하지 않습니다. 건너뜁니다.")
        return False

    # 백업 디렉토리 생성
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts             = timestamp()
    backup_path    = os.path.join(BACKUP_DIR, f"{label}_{ts}.db.bak")
    recovered_path = db_path + '.recovered'

    # 1) 원본 백업
    log(f"원본 백업 중: {backup_path}")
    shutil.copy2(db_path, backup_path)
    log(f"✅ 백업 완료: {os.path.getsize(backup_path):,} bytes")

    # 2) sqlite3 CLI로 .recover 스트리밍 복구 실행
    log("sqlite3 CLI를 사용한 스트리밍 데이터 복구 시도 중...")
    try:
        if os.path.exists(recovered_path):
            os.remove(recovered_path)

        # 디스크에 5GB SQL 덤프를 따로 저장하지 않고 바로 새 DB에 주입합니다.
        import_proc = subprocess.Popen(
            ['sqlite3', recovered_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            bufsize=1,
        )
        recover_proc = subprocess.Popen(
            ['sqlite3', db_path, '.recover'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            bufsize=1,
        )

        # 대량 쓰기 성능을 위해 새 DB 쪽은 저널/동기화를 완화합니다.
        assert import_proc.stdin is not None
        assert import_proc.stderr is not None
        assert recover_proc.stdout is not None
        assert recover_proc.stderr is not None
        import_proc.stdin.write("PRAGMA journal_mode=OFF;\n")
        import_proc.stdin.write("PRAGMA synchronous=OFF;\n")
        import_proc.stdin.write("PRAGMA temp_store=MEMORY;\n")
        import_proc.stdin.write("PRAGMA foreign_keys=OFF;\n")
        import_proc.stdin.write("PRAGMA locking_mode=EXCLUSIVE;\n")

        log("새 DB 생성 중...")

        def should_skip_recovery_statement(statement):
            """FTS5 shadow table과 books_search 관련 statement를 제외합니다."""
            normalized = re.sub(r'\s+', ' ', statement).strip()
            if not normalized:
                return True

            patterns = (
                r'^BEGIN(?:\s+TRANSACTION)?\s*;?$',
                r'^COMMIT\s*;?$',
                r'^ROLLBACK\s*;?$',
                r'^SAVEPOINT\s+\S+\s*;?$',
                r'^RELEASE\s+\S+\s*;?$',
                r'^CREATE\s+(?:VIRTUAL\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:["`\[])?books_search(?:["`\]])?(?:\s|\()',
                r'^CREATE\s+TRIGGER\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:["`\[])?books_search_',
                r'^INSERT\s+INTO\s+(?:["`\[])?books_search(?:_(?:data|idx|content|docsize|config))?(?:["`\]])?(?:\s|\()',
                r'^UPDATE\s+(?:["`\[])?books_search(?:_(?:data|idx|content|docsize|config))?(?:["`\]])?\s+SET\b',
                r'^DELETE\s+FROM\s+(?:["`\[])?books_search(?:_(?:data|idx|content|docsize|config))?(?:["`\]])?(?:\s|;|$)',
                r'^DROP\s+(?:VIRTUAL\s+)?TABLE\s+(?:IF\s+EXISTS\s+)?(?:["`\[])?books_search(?:["`\]])?(?:\s|;|$)',
                r'^ALTER\s+TABLE\s+(?:["`\[])?books_search(?:_(?:data|idx|content|docsize|config))?(?:["`\]])?',
            )
            return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns)

        def should_skip_recovery_line(line):
            """.recover 스트림의 단일 라인 제어문을 선차단합니다."""
            s = line.strip()
            if not s:
                return False

            # sqlite3 .recover 출력에 간헐적으로 섞이는 트랜잭션 제어문은
            # 스트리밍 import 쪽에서 그대로 실행하면 'cannot commit - no transaction is active'를 유발할 수 있습니다.
            txn_line_patterns = (
                r'^BEGIN(?:\s+TRANSACTION)?\s*;?$',
                r'^COMMIT\s*;?$',
                r'^ROLLBACK\s*;?$',
                r'^SAVEPOINT\s+\S+\s*;?$',
                r'^RELEASE\s+\S+\s*;?$',
                r'^END(?:\s+TRANSACTION)?\s*;?$',
            )
            return any(re.search(p, s, re.IGNORECASE) for p in txn_line_patterns)

        # 디스크 파일 없이 스트리밍으로 statement를 넘깁니다.
        try:
            skipped_statements = 0
            written_statements = 0
            statement_lines = []
            for line in recover_proc.stdout:
                if should_skip_recovery_line(line):
                    skipped_statements += 1
                    continue

                statement_lines.append(line)
                if ';' not in line:
                    continue

                statement = ''.join(statement_lines)
                statement_lines = []

                if should_skip_recovery_statement(statement):
                    skipped_statements += 1
                    continue

                import_proc.stdin.write(statement)
                written_statements += 1

            if statement_lines:
                statement = ''.join(statement_lines)
                if not should_skip_recovery_statement(statement):
                    import_proc.stdin.write(statement)
                    written_statements += 1

            recover_stderr = recover_proc.stderr.read()
            recover_rc = recover_proc.wait(timeout=300)
            if recover_rc != 0 and not recover_stderr.strip():
                log("❌ sqlite3 CLI 복구 실패: recover 단계가 실패했습니다.")
                log("→ 시스템에 sqlite3 CLI가 설치되어 있지 않거나 복구 불가 상태입니다.")
                log(f"→ 백업 파일({backup_path})을 보존합니다.")
                log("   Ubuntu/Debian: sudo apt install sqlite3")
                log("   Alpine Linux : apk add sqlite")
                return False

            import_proc.stdin.close()
            import_stderr = import_proc.stderr.read()
            import_rc = import_proc.wait(timeout=300)
            if import_rc != 0:
                log(f"❌ 복구 SQL 실행 실패 (code: {import_rc}): {import_stderr[:300]}")
                try:
                    if os.path.exists(recovered_path):
                        os.remove(recovered_path)
                        log("임시 부분 복구본 폐기 완료.")
                except Exception:
                    pass
                return False

            log(f"복구 SQL 적용 완료: {written_statements:,}개 statement 반영, {skipped_statements:,}개 FTS statement 제외")
        except Exception as import_err:
            log(f"❌ 복구 SQL 스트리밍 중 예외 발생: {import_err}")
            try:
                if 'import_proc' in locals() and import_proc.stdin and not import_proc.stdin.closed:
                    import_proc.stdin.close()
            except Exception:
                pass
            try:
                if os.path.exists(recovered_path):
                    os.remove(recovered_path)
                    log("임시 부분 복구본 폐기 완료.")
            except Exception:
                pass
            return False

        # 새 DB 무결성 및 설정 마무리
        try:
            new_conn = sqlite3.connect(recovered_path, timeout=10.0)
            new_conn.execute("PRAGMA journal_mode=WAL;")
            new_conn.execute("PRAGMA synchronous=NORMAL;")
            new_conn.commit()
            
            # 복구 DB 무결성 검증
            verify = new_conn.execute("PRAGMA integrity_check;").fetchone()
            new_conn.close()
        except Exception as db_err:
            log(f"❌ 새 DB 세팅 및 무결성 검사 중 에러: {db_err}")
            return False

        if verify and verify[0] == 'ok':
            log("✅ 복구 DB 무결성: OK")
            # 원본 교체
            os.replace(recovered_path, db_path)
            log(f"✅ [{label}] 복구 완료 — 원본 파일 교체됨")
            log(f"   백업 위치: {backup_path}")
            return True
        else:
            log(f"❌ 복구 DB 검증 실패: {verify}")
            try:
                if os.path.exists(recovered_path):
                    os.remove(recovered_path)
                    log("임시 부분 복구본 폐기 완료.")
            except Exception:
                pass
            return False

    except FileNotFoundError:
        log("❌ sqlite3 CLI를 찾을 수 없습니다.")
        log("   Ubuntu/Debian: sudo apt install sqlite3")
        log("   Alpine Linux : apk add sqlite")
        return False
    except Exception as e:
        log(f"❌ 복구 중 오류: {e}")
        return False

def rebuild_fts_index(db_path, label):
    """
    구형 FTS5 가상 테이블 및 그림자 테이블을 완전히 소거합니다.
    """
    sep()
    log(f"[{label}] 구형 FTS5 가상 테이블 소거 작업 시작", prefix='')
    
    if not os.path.exists(db_path):
        log("⚠️  DB 파일이 존재하지 않습니다. 건너뜁니다.")
        return False

    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        from database import cleanup_legacy_fts_index
        cleanup_legacy_fts_index(conn)
        conn.close()
        log("✅ 구형 FTS5 가상 테이블 소거 완료.")
        return True
    except Exception as e:
        log(f"⚠️  소거 진행 중 참고 안내: {e}")
        return False

# ─────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="BookOasis DB 복구 스크립트")
    parser.add_argument('--db', type=str, help="복구할 특정 DB 파일 경로 (예: test/chinh_media_general.db)")
    parser.add_argument('--yes', action='store_true', help="확인 프롬프트를 건너뛰고 바로 진행")
    args = parser.parse_args()

    # DB_FILES 재구성
    if args.db:
        db_path = os.path.abspath(args.db)
        label = os.path.splitext(os.path.basename(db_path))[0]
        target_db_files = {label: db_path}
    else:
        target_db_files = DB_FILES

    sep('=')
    print("  BookOasis DB 복구 스크립트")
    print(f"  실행 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.db:
        print(f"  대상 DB  : {args.db}")
    else:
        print(f"  DB 경로  : {DB_DIR}")
    sep('=')
    print()

    print("⚠️  주의사항")
    print("  이 스크립트 실행 전 BookOasis 서버(컨테이너)가")
    print("  완전히 정지되어 있는지 반드시 확인하세요.")
    print("  실행 중인 서버와 동시에 사용 시 DB가 추가 손상될 수 있습니다.")
    print()

    if not args.yes:
        confirm = input("  계속 진행하려면 'yes'를 입력하세요: ").strip().lower()
        if confirm != 'yes':
            print("  취소되었습니다.")
            sys.exit(0)
    else:
        print("  [--yes] 옵션으로 인해 확인 프롬프트를 건너뜁니다.")

    print()

    # ── STEP 1: WAL 체크포인트 시도 ──
    sep('=')
    print("  STEP 1 — WAL 체크포인트 (데이터 손실 없음)")
    sep('=')

    step1_results = {}
    for label, db_path in target_db_files.items():
        ok = step1_wal_checkpoint(db_path, label)
        step1_results[label] = ok

    print()

    # ── STEP 1 실패한 DB가 있으면 STEP 2 안내 ──
    failed = [label for label, ok in step1_results.items() if not ok]
    if failed:
        sep('=')
        print("  STEP 2 — 전체 복구 (손상 DB 재생성)")
        sep('=')
        print(f"  Step 1 실패 항목: {', '.join(failed)}")
        print("  Step 2는 복구 가능한 데이터를 추출하여 DB를 재생성합니다.")
        print("  최근 일부 변경사항(읽기 진행률 등)이 손실될 수 있습니다.")
        print()
        
        if args.yes:
            confirm2 = 'yes'
            print("  [--yes] 옵션으로 인해 Step 2를 바로 진행합니다.")
        else:
            confirm2 = input("  Step 2를 계속 진행하려면 'yes'를 입력하세요: ").strip().lower()
            
        if confirm2 == 'yes':
            for label in failed:
                step2_full_recovery(target_db_files[label], label)
        else:
            print("  Step 2를 건너뜁니다.")

    # ── STEP 3: 구형 FTS5 가상 테이블 디스크 잔여물 완전 정돈 ──
    print()
    sep('=')
    print("  STEP 3 — 구형 FTS5 가상 테이블 디스크 완전 정돈")
    sep('=')
    for label, db_path in target_db_files.items():
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path, timeout=10.0)
                from database import cleanup_legacy_fts_index
                cleanup_legacy_fts_index(conn)
                conn.close()
                log(f"[{label}] 구형 FTS5 테이블 디스크 정리 완료.")
            except Exception as fts_clean_err:
                log(f"[{label}] 구형 FTS5 정리 통과: {fts_clean_err}")

    # ── 최종 상태 요약 ──
    print()
    sep('=')
    print("  복구 작업 완료 — 최종 상태 확인")
    sep('=')
    for label, db_path in target_db_files.items():
        if os.path.exists(db_path):
            try:
                conn   = sqlite3.connect(db_path, timeout=5.0)
                result = conn.execute("PRAGMA integrity_check;").fetchone()
                conn.close()
                status = "✅ OK" if result and result[0] == 'ok' else f"❌ {result}"
            except Exception as e:
                status = f"❌ 접속 실패: {e}"
        else:
            status = "⚠️  파일 없음"
        log(f"[{label}] 최종 상태: {status}")

    print()
    print("  복구가 완료되었으면 서버를 재시작하세요:")
    print("    $ docker start bookoasis")
    print()

if __name__ == '__main__':
    main()
