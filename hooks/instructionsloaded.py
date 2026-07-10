#!/usr/bin/env python3
"""nunchi InstructionsLoaded 엔트리포인트 — 세션 관측 기록 (#10).

CLAUDE.md/.claude/rules가 컨텍스트에 로드될 때마다 발화하므로 모든 세션을
잡는다. 세션당 1줄만 기록한다(record_session이 마커로 dedupe).
어떤 실패도 exit 0. stdout은 컨텍스트에 주입되므로 절대 아무것도 쓰지 않는다.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    from core.engine import record_session

    input_data = json.load(sys.stdin)
    project_dir = (
        os.environ.get("CLAUDE_PROJECT_DIR") or input_data.get("cwd") or os.getcwd()
    )
    record_session(input_data, project_dir)
except Exception as e:
    print(f"nunchi: instructionsloaded hook error: {e}", file=sys.stderr)
sys.exit(0)
