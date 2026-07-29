# tools/scanner/ignore_filter.py
import os
import fnmatch

DEFAULT_IGNORE_PATTERNS = [
    "@eaDir/",
    "#recycle/",
    "*.tmp",
    "*.sample.cbz",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    ".git/",
    ".svn/"
]

def _parse_pattern(line):
    line = line.strip()
    if not line:
        return None
    # # 으로 시작하는 주석 무시 (#recycle 예외 처리)
    if line.startswith('#') and not line.lower().startswith('#recycle'):
        return None
    
    is_dir_only = line.endswith('/')
    clean_pat = line.rstrip('/')
    if not clean_pat:
        return None
    return (clean_pat, is_dir_only, line)

class IgnoreFilter:
    def __init__(self, global_pattern_str=None):
        self.global_patterns = []  # list of (clean_pat, is_dir_only, raw_line)
        if global_pattern_str:
            self.add_global_patterns(global_pattern_str)
        else:
            for pat in DEFAULT_IGNORE_PATTERNS:
                parsed = _parse_pattern(pat)
                if parsed:
                    self.global_patterns.append(parsed)
                    
        self.dir_patterns = {}  # base_dir -> list of (clean_pat, is_dir_only, raw_line)

    def add_global_patterns(self, pattern_str):
        if not pattern_str:
            return
        lines = [line.strip() for line in pattern_str.splitlines()]
        for line in lines:
            parsed = _parse_pattern(line)
            if parsed and parsed not in self.global_patterns:
                self.global_patterns.append(parsed)

    def load_ignore_file(self, file_path, base_dir=None):
        if not os.path.exists(file_path):
            return
        base_dir = os.path.normpath(base_dir or os.path.dirname(file_path)).replace('\\', '/')
        patterns = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    parsed = _parse_pattern(line)
                    if parsed:
                        patterns.append(parsed)
        except Exception as e:
            print(f"[IgnoreFilter] Warning reading {file_path}: {e}")
            return

        if patterns:
            self.dir_patterns[base_dir] = patterns

    def should_ignore_dir(self, dir_name, parent_path=None):
        if not dir_name:
            return False

        d_name_lower = dir_name.lower()
        for clean_pat, _, _ in self.global_patterns:
            p_lower = clean_pat.lower()
            if d_name_lower == p_lower or fnmatch.fnmatch(d_name_lower, p_lower):
                return True

        if parent_path:
            norm_parent = os.path.normpath(parent_path).replace('\\', '/')
            for base_dir, patterns in self.dir_patterns.items():
                if norm_parent == base_dir or norm_parent.startswith(base_dir + '/'):
                    for clean_pat, _, _ in patterns:
                        p_lower = clean_pat.lower()
                        if d_name_lower == p_lower or fnmatch.fnmatch(d_name_lower, p_lower):
                            return True

        return False

    def should_ignore_file(self, file_name, parent_path=None):
        if not file_name:
            return False

        f_name_lower = file_name.lower()
        if f_name_lower == '.bookoasisignore':
            return True

        for clean_pat, is_dir_only, _ in self.global_patterns:
            if is_dir_only:
                continue  # 디렉토리 전용 규칙(패턴 끝 /)은 파일 매칭에서 제외
            p_lower = clean_pat.lower()
            if f_name_lower == p_lower or fnmatch.fnmatch(f_name_lower, p_lower):
                return True

        if parent_path:
            norm_parent = os.path.normpath(parent_path).replace('\\', '/')
            for base_dir, patterns in self.dir_patterns.items():
                if norm_parent == base_dir or norm_parent.startswith(base_dir + '/'):
                    for clean_pat, is_dir_only, _ in patterns:
                        if is_dir_only:
                            continue
                        p_lower = clean_pat.lower()
                        if f_name_lower == p_lower or fnmatch.fnmatch(f_name_lower, p_lower):
                            return True

        return False
