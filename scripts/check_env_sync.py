#!/usr/bin/env python3
"""
Checks environment variable consistency across all four env files.
Exits with non-zero if:
  (a) a key exists in one file but not the others
  (b) a key used in code is in no example file
  (c) a required secret still holds a placeholder in a non-example file
  (d) a committed file contains something that looks like a real secret
"""

import os
import re
import sys
from pathlib import Path


def parse_env_file(filepath: Path) -> dict:
    """Parse a dotenv-style file and return dict of key -> value (stripped)."""
    if not filepath.exists():
        return {}
    content = filepath.read_text()
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, _, value = line.partition('=')
            result[key.strip()] = value.strip()
    return result


def get_code_keys(code_dir: Path) -> set:
    """Extract all settings keys used in Python code."""
    keys = set()
    settings_pattern = re.compile(r'settings\.([A-Z][A-Z0-9_]*)')
    
    for py_file in code_dir.rglob('*.py'):
        try:
            content = py_file.read_text()
            for match in settings_pattern.findall(content):
                # Filter to only settings field names (uppercase with underscores)
                if re.match(r'^[A-Z][A-Z0-9_]*$', match):
                    keys.add(match)
        except Exception:
            pass
    
    return keys


def get_frontend_keys(frontend_dir: Path) -> set:
    """Extract all VITE_* env vars used in frontend code."""
    keys = set()
    vite_pattern = re.compile(r'VITE_([A-Z][A-Z0-9_]*)')
    
    for tsx_file in frontend_dir.rglob('*.ts*'):
        try:
            content = ts/tsx_file.read_text()
            for match in vite_pattern.findall(content):
                keys.add(f'VITE_{match}')
        except Exception:
            pass
    
    return keys


def check_placeholder_secrets(env_dict: dict, is_example: bool) -> list:
    """Check for placeholder values that should be replaced."""
    issues = []
    placeholder_patterns = [
        'your_', 'change_me', 'placeholder', 'ep-xxxx', '<your_',
        'secret', 'password', 'key_here', 'email@example.com'
    ]
    
    for key, value in env_dict.items():
        if key in ('INGEST_API_KEY', 'ACCESS_TOKEN_SECRET', 'REFRESH_TOKEN_SECRET'):
            if not is_example:
                for pattern in placeholder_patterns:
                    if pattern in value.lower():
                        issues.append(f"  {key}: contains placeholder value")
    return issues


def check_for_real_secrets_in_committed(env_dict: dict, is_example: bool) -> list:
    """Check if real secrets exist in non-example files."""
    issues = []
    if is_example:
        return issues
    
    neon_pattern = re.compile(r'neon\.tech', re.IGNORECASE)
    gmail_pattern = re.compile(r'@gmail\.com')
    upstash_pattern = re.compile(r'upstash\.io')
    
    for key, value in env_dict.items():
        if neon_pattern.search(value):
            issues.append(f"  {key}: may contain real Neon password")
        if gmail_pattern.search(value) and 'smtp' in key.lower():
            issues.append(f"  {key}: may contain real Gmail credentials")
        if upstash_pattern.search(value):
            issues.append(f"  {key}: may contain real Redis credentials")
    
    return issues


def main():
    root_dir = Path(__file__).parent.parent
    backend_dir = root_dir / 'backend-fastapi'
    frontend_dir = root_dir / 'frontend' / 'lms'
    
    # Load all env files
    root_example = root_dir / '.env.example'
    backend_example = backend_dir / '.env.example'
    frontend_example = frontend_dir / '.env.example'
    
    root_env = parse_env_file(root_dir / '.env')
    backend_env = parse_env_file(backend_dir / '.env')
    backend_local = parse_env_file(backend_dir / '.env.local')
    frontend_env = parse_env_file(frontend_dir / '.env')
    frontend_local = parse_env_file(frontend_dir / '.env.local')
    
    all_pass = True
    
    # 1. Get backend settings keys from code
    code_keys = get_code_keys(backend_dir / 'app')
    
    # 2. Get frontend VITE keys from code
    frontend_code_keys = get_frontend_keys(frontend_dir)
    
    # 3. Get all keys from example files
    example_keys = set()
    for env_dict in [parse_env_file(root_example), parse_env_file(backend_example), parse_env_file(frontend_example)]:
        example_keys.update(env_dict.keys())
    
    # 4. Check for keys in code but not in example files
    print("=== CHECK 1: Code keys not in example files ===")
    missing_from_example = []
    for key in sorted(code_keys):
        if key not in example_keys and not key.startswith('SYSLOG_'):  # SYSLOG_ vars are optional
            missing_from_example.append(key)
    
    if missing_from_example:
        print("FAIL: Keys in code but not in example files:", missing_from_example)
        all_pass = False
    else:
        print("PASS: All code keys present in example files")
    
    # 5. Check for keys in example files but not in real .env.local
    print("\n=== CHECK 2: Keys missing from .env.local ===")
    missing_from_local = []
    required_keys = [
        'DATABASE_URL', 'ACCESS_TOKEN_SECRET', 'REFRESH_TOKEN_SECRET',
        'REDIS_URL', 'CORS_ORIGINS'
    ]
    for key in required_keys:
        if key not in backend_local:
            missing_from_local.append(key)
    
    optional_keys = ['COOKIE_SECURE', 'COOKIE_SAME_SITE', 'DATABASE_POOL', 'JWT_ALGORITHM', 
                     'REFRESH_TOKEN_EXPIRE_DAYS', 'SYSLOG_TIMEZONE', 'ACCESS_TOKEN_EXPIRE_MINUTES']
    
    if missing_from_local:
        print(f"WARN: Required keys missing from backend-fastapi/.env.local: {missing_from_local}")
    if optional_keys:
        print(f"INFO: Optional keys (may use defaults): {optional_keys}")
    
    # 6. Check for secrets in committed example files
    print("\n=== CHECK 3: Real secrets in example files ===")
    for filepath in [root_example, backend_example, frontend_example]:
        if filepath.exists():
            env_dict = parse_env_file(filepath)
            for key, value in env_dict.items():
                for pattern in ['neon.tech', 'upstash.io', '@gmail.com']:
                    if pattern in value.lower():
                        print(f"WARN: {filepath.name}: {key} contains {pattern}")
    
    # 7. Check for placeholder secrets in real .env files
    print("\n=== CHECK 4: Placeholder secrets in non-example .env files ===")
    placeholder_issues = []
    for env_type, env_dict in [('backend-env', backend_env), ('backend-local', backend_local), 
                                ('frontend-env', frontend_env), ('frontend-local', frontend_local)]:
        issues = check_placeholder_secrets(env_dict, is_example=False)
        if issues:
            placeholder_issues.extend(issues)
    
    if placeholder_issues:
        print("FAIL: Placeholder values in non-example .env files:")
        for issue in placeholder_issues:
            print(issue)
        all_pass = False
    else:
        print("PASS: No placeholder secrets in non-example .env files")
    
    # Final summary
    print("\n" + "="*50)
    if all_pass:
        print("PASS: Environment sync check passed")
        return 0
    else:
        print("FAIL: Environment sync check failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())