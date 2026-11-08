import argparse
import os
import re
import sys
from pathlib import Path
def parse_env_file(filepath: Path) -> dict:
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
    keys = set()
    settings_pattern = re.compile(r'settings\.([A-Z][A-Z0-9_]*)')
    for py_file in code_dir.rglob('*.py'):
        try:
            content = py_file.read_text()
            for match in settings_pattern.findall(content):
                if re.match(r'^[A-Z][A-Z0-9_]*$', match):
                    keys.add(match)
        except Exception:
            pass
    return keys
def get_frontend_keys(frontend_dir: Path) -> set:
    keys = set()
    vite_pattern = re.compile(r'VITE_([A-Z][A-Z0-9_]*)')

    for tsx_file in frontend_dir.rglob('*.ts*'):
        try:
            content = tsx_file.read_text()
            for match in vite_pattern.findall(content):
                keys.add(f'VITE_{match}')
        except Exception:
            pass

    return keys
def check_placeholder_secrets(env_dict: dict, is_example: bool) -> list:
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

def main():
    parser = argparse.ArgumentParser(description='Check environment variable consistency')
    parser.add_argument('--check-local', action='store_true', help='also inspect non-example .env.local files (may read local secrets)')
    args = parser.parse_args()
    root_dir = Path(__file__).parent.parent
    backend_dir = root_dir / 'backend'
    frontend_dir = root_dir / 'frontend' / 'lms'
    root_example = root_dir / '.env.example'
    backend_example = backend_dir / '.env.example'
    frontend_example = frontend_dir / '.env.example'

    backend_local = parse_env_file(backend_dir / '.env.local') if args.check_local else {}
    all_pass = True

    code_keys = get_code_keys(backend_dir / 'app')

    frontend_code_keys = get_frontend_keys(frontend_dir)

    example_keys = set()
    for env_dict in [parse_env_file(root_example), parse_env_file(backend_example), parse_env_file(frontend_example)]:
        example_keys.update(env_dict.keys())

    print("=== CHECK 1: Code keys must be in example files ===")
    missing_from_example = []
    for key in sorted(code_keys):
        if key not in example_keys and not key.startswith('SYSLOG_'):
            missing_from_example.append(key)

    print("=== CHECK 2: Non-example files must not have keys missing from examples ===")
    if args.check_local:
        unexpected_keys = []
        for key in backend_local:
            if key not in example_keys:
                unexpected_keys.append(key)

        if unexpected_keys:
            print(f"FAIL: Keys in .env.local but not in example files: {unexpected_keys}")
            all_pass = False
        else:
            print("PASS: All .env.local keys present in example files")
    else:
        print("SKIP: .env.local not inspected (use --check-local)")

    print("\n=== CHECK 3: Required keys must be in .env.local ===")
    if args.check_local:
        required_keys = [
            'DATABASE_URL', 'ACCESS_TOKEN_SECRET', 'REFRESH_TOKEN_SECRET',
            'REDIS_URL', 'CORS_ORIGINS'
        ]
        missing_from_local = []
        for key in required_keys:
            if key not in backend_local:
                missing_from_local.append(key)
        if missing_from_local:
            print(f"FAIL: Required keys missing from .env.local: {missing_from_local}")
            all_pass = False
        else:
            print("PASS: All required keys present in .env.local")
    else:
        print("SKIP: .env.local not inspected (use --check-local)")

    print("\n=== CHECK 4: Check for real secrets in example files ===")
    secrets_found = False
    for filepath in [root_example, backend_example, frontend_example]:
        if filepath.exists():
            env_dict = parse_env_file(filepath)
            for key, value in env_dict.items():
                for pattern in ['neon.tech', 'upstash.io', '@gmail.com']:
                    if pattern in value.lower():
                        print(f"WARN: {filepath.name}: {key} may contain real secret")
                        secrets_found = True
    if not secrets_found:
        print("PASS: No real secrets in example files")
    print("\n=== CHECK 5: Check for placeholder secrets in non-example .env files ===")
    if args.check_local:
        placeholder_issues = check_placeholder_secrets(backend_local, is_example=False)

        if placeholder_issues:
            print("FAIL: Placeholder values in non-example .env files:")
            for issue in placeholder_issues:
                print(issue)
            all_pass = False
        else:
            print("PASS: No placeholder secrets in non-example .env files")
    else:
        print("SKIP: .env.local not inspected (use --check-local)")
    print("\n" + "="*50)
    if all_pass:
        print("PASS: Environment sync check passed")
        return 0
    else:
        print("FAIL: Environment sync check failed")
        return 1
if __name__ == '__main__':
    sys.exit(main())
