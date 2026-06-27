#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
미디어 서버 (BookOasis) - 통합 문서 수집 및 이력 보존 스크립트
작성일: 2026-06-19
"""

import os
import sys
import re
import shutil
import argparse
from datetime import datetime
from dotenv import load_dotenv

# .env 로드
load_dotenv()

PROJECT_NAME = "BookOasis"
DOCS_COLLECT_PATH = os.getenv("DOCS_COLLECT_PATH", "")

def get_current_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def get_current_date():
    return datetime.now().strftime("%Y-%m-%d")

def ensure_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

def parse_yaml_front_matter(content):
    """
    마크다운 내용에서 YAML Front Matter를 파싱합니다.
    """
    pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(pattern, content, re.DOTALL)
    if match:
        front_matter = match.group(1)
        body = content[match.end():]
        # 단순 딕셔너리 파싱
        metadata = {}
        for line in front_matter.split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                metadata[key.strip()] = val.strip().strip('"').strip("'")
        return metadata, body
    return {}, content

def build_yaml_front_matter(metadata):
    """
    딕셔너리를 YAML Front Matter 형태로 변환합니다.
    """
    fm_lines = ["---"]
    for k, v in metadata.items():
        fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    return "\n".join(fm_lines) + "\n"

def archive_session_files(keyword, summary):
    """
    task.md 및 walkthrough.md를 docs/history/ 디렉터리에 아카이빙하고
    docs/workflow.md에 히스토리를 누적 기록합니다.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    task_file = os.path.join(project_root, "task.md")
    walkthrough_file = os.path.join(project_root, "walkthrough.md")
    history_dir = os.path.join(project_root, "docs", "history")
    workflow_file = os.path.join(project_root, "docs", "workflow.md")
    
    timestamp = get_current_timestamp()
    date_str = get_current_date()
    
    archived_task_name = f"{timestamp}_{keyword}_task.md"
    archived_walkthrough_name = f"{timestamp}_{keyword}_walkthrough.md"
    
    archived_task_path = os.path.join(history_dir, archived_task_name)
    archived_walkthrough_path = os.path.join(history_dir, archived_walkthrough_name)
    
    # 디렉터리 보장
    ensure_directory(history_dir)
    
    task_archived = False
    walkthrough_archived = False
    
    # 1. task.md 아카이빙
    if os.path.exists(task_file):
        with open(task_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        metadata, body = parse_yaml_front_matter(content)
        metadata.update({
            "title": f"Task - {keyword}",
            "project": PROJECT_NAME,
            "category": "history",
            "date": date_str,
            "type": "task"
        })
        
        new_content = build_yaml_front_matter(metadata) + body
        with open(archived_task_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        task_archived = True
        print(f"[아카이브] task.md 저장 완료 -> {archived_task_name}")
        
    # 2. walkthrough.md 아카이빙
    if os.path.exists(walkthrough_file):
        with open(walkthrough_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        metadata, body = parse_yaml_front_matter(content)
        metadata.update({
            "title": f"Walkthrough - {keyword}",
            "project": PROJECT_NAME,
            "category": "history",
            "date": date_str,
            "type": "walkthrough"
        })
        
        new_content = build_yaml_front_matter(metadata) + body
        with open(archived_walkthrough_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        walkthrough_archived = True
        print(f"[아카이브] walkthrough.md 저장 완료 -> {archived_walkthrough_name}")

    # 3. docs/workflow.md 갱신
    if task_archived or walkthrough_archived:
        # 파일이 없으면 초기 양식 작성
        if not os.path.exists(workflow_file):
            with open(workflow_file, "w", encoding="utf-8") as f:
                f.write(f"""# 📈 프로젝트 작업 이력 (Workflow History)

이 문서는 프로젝트의 작업 세션 이력을 기록한 마스터 파일입니다.

| 날짜 | 세션 키워드 | 한 줄 요약 | 태스크 문서 | 워크쓰루 문서 |
| :--- | :--- | :--- | :--- | :--- |
""")
        
        # 새로운 행 추가
        task_link = f"[Task](./history/{archived_task_name})" if task_archived else "-"
        walkthrough_link = f"[Walkthrough](./history/{archived_walkthrough_name})" if walkthrough_archived else "-"
        
        new_row = f"| {date_str} | `{keyword}` | {summary} | {task_link} | {walkthrough_link} |\n"
        
        with open(workflow_file, "a", encoding="utf-8") as f:
            f.write(new_row)
        print(f"[업데이트] workflow.md 이력 기록 완료: {summary}")

    return archived_task_name, archived_walkthrough_name

def process_and_collect_docs(test_mode=False):
    """
    docs/ 폴더 하위의 문서를 수집 서버 경로로 가공하여 복사합니다.
    """
    if not DOCS_COLLECT_PATH:
        print("[경고] DOCS_COLLECT_PATH 환경변수가 설정되지 않아 수집 전송을 건너뜁니다.")
        return
        
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    src_docs_dir = os.path.join(project_root, "docs")
    dest_docs_dir = os.path.join(DOCS_COLLECT_PATH, PROJECT_NAME)
    dest_assets_dir = os.path.join(DOCS_COLLECT_PATH, "assets", PROJECT_NAME)
    
    if test_mode:
        print(f"[테스트 모드] 수집 타겟 경로: {dest_docs_dir}")
        print(f"[테스트 모드] 리소스 타겟 경로: {dest_assets_dir}")
        return
        
    ensure_directory(dest_docs_dir)
    ensure_directory(dest_assets_dir)
    
    print(f"[수집 시작] {src_docs_dir} -> {dest_docs_dir}")
    
    # 1. docs/ 폴더 내 파일 순회
    for root, dirs, files in os.walk(src_docs_dir):
        # 복사 대상 상대 경로 계산
        rel_path = os.path.relpath(root, src_docs_dir)
        target_subdir = dest_docs_dir if rel_path == "." else os.path.join(dest_docs_dir, rel_path)
        ensure_directory(target_subdir)
        
        for file in files:
            src_file_path = os.path.join(root, file)
            dest_file_path = os.path.join(target_subdir, file)
            
            # 마크다운 파일인 경우 파싱 및 변환 처리
            if file.endswith(".md"):
                with open(src_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # A. Front Matter 주입
                metadata, body = parse_yaml_front_matter(content)
                
                # 기본 정보 설정
                if "project" not in metadata:
                    metadata["project"] = PROJECT_NAME
                if "title" not in metadata:
                    # 타이틀이 없으면 파일 이름으로 대체
                    title_name = os.path.splitext(file)[0].replace("_", " ").title()
                    metadata["title"] = title_name
                if "date" not in metadata:
                    mtime = os.path.getmtime(src_file_path)
                    metadata["date"] = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                if "category" not in metadata:
                    # 상위 폴더 이름이나 파일명 패턴으로 카테고리 정의
                    if "bug" in root:
                        metadata["category"] = "bug"
                    elif "history" in root:
                        metadata["category"] = "history"
                    elif file.startswith("spec_"):
                        metadata["category"] = "spec"
                    else:
                        metadata["category"] = "general"
                
                # B. 이미지 경로 치환 및 이관
                # 패턴: ![alt](./docs/images/xxx.png) 또는 src="./docs/images/xxx.png" 등
                # 타겟: /assets/BookOasis/xxx.png로 치환하고 실물 복사
                img_patterns = [
                    (r'!\[(.*?)\]\((.*?)\)', r'![\1](\2)'),
                    (r'src=["\'](.*?)["\']', r'src="\1"')
                ]
                
                def img_replacer(match):
                    full_match = match.group(0)
                    img_path = match.group(1) if len(match.groups()) == 1 else match.group(2)
                    
                    # 로컬 docs/images 경로 감지
                    # 예: ./docs/images/xxx.png, /docs/images/xxx.png, docs/images/xxx.png 등
                    if "docs/images/" in img_path:
                        img_filename = os.path.basename(img_path)
                        # 원본 이미지 위치 추정
                        src_img_path = os.path.join(src_docs_dir, "images", img_filename)
                        if os.path.exists(src_img_path):
                            # 타겟 에셋 폴더로 실물 파일 복사
                            dest_img_path = os.path.join(dest_assets_dir, img_filename)
                            shutil.copy2(src_img_path, dest_img_path)
                            
                            # 본문 내 주소 치환
                            new_web_path = f"/assets/{PROJECT_NAME}/{img_filename}"
                            return full_match.replace(img_path, new_web_path)
                        else:
                            print(f"[경고] 이미지 파일 실물이 존재하지 않습니다: {src_img_path}")
                    return full_match
                
                # 정규식 기반 치환
                # Markdown 이미지 치환
                body = re.sub(r'!\[(.*?)\]\((.*?)\)', img_replacer, body)
                # HTML src 치환
                body = re.sub(r'src=["\'](.*?)["\']', img_replacer, body)
                
                # C. 문서 상호 참조 링크 보강 (./파일명.md 형식으로 정리)
                
                new_content = build_yaml_front_matter(metadata) + body
                
                with open(dest_file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                
            else:
                # 마크다운이 아닌 기타 파일(예: 이미지 등)은 직접 복사 (다만 이미지는 assets로 분리했으므로 생략해도 됨)
                if not file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
                    shutil.copy2(src_file_path, dest_file_path)
                    
    print(f"[수집 완료] 통합 문서 디렉터리 최신화가 완료되었습니다.")

def update_mkdocs_nav():
    import yaml
    print("\n[*] mkdocs.yml 네비게이션 자동 생성 중...")
    try:
        with open('mkdocs.yml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        nav = [
            {"위키 홈": "index.md"},
            {"개발 워크플로우": "workflow.md"}
        ]
        
        # 작업 히스토리 수집 (최신순 정렬)
        if os.path.exists('docs/history'):
            history_files = [f"history/{f}" for f in sorted(os.listdir('docs/history'), reverse=True) if f.endswith('.md') and f != 'index.md']
            if history_files:
                # index.md를 첫 번째로 넣기
                history_nav = ["history/index.md"] + history_files
                nav.append({"작업 히스토리": history_nav})
            else:
                nav.append({"작업 히스토리": "history/index.md"})

        # 버그 트러블슈팅 수집 (최신순 정렬)
        if os.path.exists('docs/bug'):
            bug_files = [f"bug/{f}" for f in sorted(os.listdir('docs/bug'), reverse=True) if f.endswith('.md') and f != 'index.md']
            if bug_files:
                bug_nav = ["bug/index.md"] + bug_files
                nav.append({"버그 트러블슈팅": bug_nav})
            else:
                nav.append({"버그 트러블슈팅": "bug/index.md"})

        config['nav'] = nav

        with open('mkdocs.yml', 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print("[+] mkdocs.yml nav 자동 구성 완료!")
    except Exception as e:
        print(f"[!] mkdocs.yml 업데이트 실패: {e}")

def main():
    parser = argparse.ArgumentParser(description="미디어 서버 - 문서 수집 및 이력 보존 도구")
    parser.add_argument("-k", "--keyword", help="작업 세션 키워드 (예: fix_audio_bug)")
    parser.add_argument("-s", "--summary", help="작업 세션에 대한 한 줄 요약")
    parser.add_argument("--test", action="store_true", help="수집 서버 복사 작업을 모의 실행(Dry-run)합니다.")
    
    args = parser.parse_args()
    
    keyword = args.keyword
    summary = args.summary
    
    # 인터랙티브 모드 또는 기본값 처리
    if not keyword:
        if sys.stdin.isatty():
            try:
                keyword = input("세션 키워드를 입력하세요: ").strip()
            except KeyboardInterrupt:
                print("\n중단되었습니다.")
                sys.exit(1)
        if not keyword:
            keyword = f"session_{get_current_timestamp()}"
            
    if not summary:
        if sys.stdin.isatty():
            try:
                summary = input("작업 내용 한 줄 요약을 입력하세요: ").strip()
            except KeyboardInterrupt:
                print("\n중단되었습니다.")
                sys.exit(1)
        if not summary:
            summary = "마크다운 문서 이력 아카이빙 및 동기화"
            
    print(f"\n==========================================")
    print(f" 프로젝트: {PROJECT_NAME}")
    print(f" 세션 키워드: {keyword}")
    print(f" 한 줄 요약: {summary}")
    print(f" 수집 경로: {DOCS_COLLECT_PATH or '미지정'}")
    print(f"==========================================\n")
    
    # 1. task.md & walkthrough.md 아카이빙 실행
    archive_session_files(keyword, summary)
    
    # 2. 문서 수집 및 치환 복사 실행
    process_and_collect_docs(test_mode=args.test)

    # 3. mkdocs.yml nav 자동 업데이트
    if not args.test:
        update_mkdocs_nav()

if __name__ == "__main__":
    main()
