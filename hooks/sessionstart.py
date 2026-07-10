#!/usr/bin/env python3
"""nunchi SessionStart(compact) 엔트리포인트 — 배달 마커 재무장.

어떤 실패도 exit 0. stdout은 컨텍스트에 주입되므로 절대 아무것도 쓰지 않는다.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    from core.engine import rearm

    input_data = json.load(sys.stdin)
    # hooks.json의 matcher("compact")가 1차 방어, 코드 가드가 2차 방어.
    if input_data.get("source") == "compact":
        project_dir = (
            os.environ.get("CLAUDE_PROJECT_DIR") or input_data.get("cwd") or os.getcwd()
        )
        rearm(input_data, project_dir)
except Exception as e:
    print(f"nunchi: sessionstart hook error: {e}", file=sys.stderr)
sys.exit(0)
