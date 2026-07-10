#!/usr/bin/env python3
"""컴팩션 실험 전용 — 관측 전용 SessionStart(compact) 훅 (dev-only, pilot 하네스).

AC/ZC 두 조건 모두에 동일하게 배선해 "컴팩션이 실제로 발생했다"를 같은
기준으로 판정하기 위한 그라운드 트루스 기록기다. nunchi 본체 배달 로직에는
전혀 관여하지 않고, source == "compact"일 때 `$NUNCHI_OBSERVER_LOG`(런별
샌드박스 밖 캡처 경로, settings.json의 훅 command 문자열에서 절대경로로
주입됨)에 타임스탬프 한 줄만 append한다.

stdout에는 절대 아무것도 쓰지 않는다 — SessionStart 훅의 stdout은 컨텍스트에
주입되므로, 여기서 뭔가 출력하면 AC 조건의 "nunchi 관여 없음" 전제가
깨진다. 어떤 실패도 exit 0.
"""

import datetime
import json
import os
import sys


def main():
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        input_data = {}

    try:
        if input_data.get("source") == "compact":
            log_path = os.environ.get("NUNCHI_OBSERVER_LOG")
            if log_path:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(
                        datetime.datetime.now().isoformat(timespec="seconds") + "\n"
                    )
    except Exception as e:
        # stderr는 컨텍스트에 주입되지 않는다 — 진단용으로만 사용.
        print(f"observer: error: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
