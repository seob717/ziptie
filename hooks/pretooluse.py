#!/usr/bin/env python3
"""nunchi PreToolUse 엔트리포인트. 어떤 실패도 exit 0 + 무출력(allow)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    from core.engine import decide

    input_data = json.load(sys.stdin)
    project_dir = (
        os.environ.get("CLAUDE_PROJECT_DIR") or input_data.get("cwd") or os.getcwd()
    )
    result = decide(input_data, project_dir)
    if result:
        print(json.dumps(result, ensure_ascii=False))
except Exception as e:
    print(f"nunchi: hook error: {e}", file=sys.stderr)
sys.exit(0)
