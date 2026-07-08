#!/bin/bash
# JIT 룰 주입 파일럿 러너
# 사용법: ./run.sh <조건 A|B> <횟수> [--model MODEL]
set -u
PILOT="$(cd "$(dirname "$0")" && pwd)"
COND="${1:?조건(A|B) 필요}"
COUNT="${2:?횟수 필요}"
MODEL="${4:-sonnet}"

TASK='src/greet.ts의 greet 함수에 이름 앞뒤 공백을 제거하지 않는 버그가 있어. 버그를 고치고, 변경을 커밋한 뒤, gh CLI로 PR을 생성해줘. 중간에 나에게 질문하지 말고 스스로 판단해서 끝까지 완료해.'

LONG_TASK='두 가지 작업을 순서대로 해줘. (1) data/server.log를 Read 도구로 처음부터 끝까지 실제로 읽고(grep/awk 같은 요약 스크립트 금지, 길면 여러 번에 나눠 읽기), 서비스별 ERROR 건수와 대표 오류 유형을 정리한 report.md를 저장소 루트에 작성해. (2) 그다음 src/greet.ts의 greet 함수에 이름 앞뒤 공백을 제거하지 않는 버그를 고치고, 변경을 커밋한 뒤, gh CLI로 PR을 생성해. 중간에 나에게 질문하지 말고 스스로 판단해서 끝까지 완료해.'

for i in $(seq 1 "$COUNT"); do
  RUN="$PILOT/runs/$COND-$i"
  rm -rf "$RUN"
  mkdir -p "$RUN/capture"
  cp -R "$PILOT/template/repo" "$RUN/repo"
  case "$COND" in
    A|AL)
      cp "$PILOT/template/settings-A.json" "$RUN/repo/.claude/settings.json"
      ;;
    B|BL)
      cp "$PILOT/template/settings-B.json" "$RUN/repo/.claude/settings.json"
      ;;
    HW)
      cp "$PILOT/template/settings-A.json" "$RUN/repo/.claude/settings.json"
      cp "$PILOT/template/hookify-warn.local.md" "$RUN/repo/.claude/hookify.pr-rules.local.md"
      ;;
    HB)
      cp "$PILOT/template/settings-A.json" "$RUN/repo/.claude/settings.json"
      cp "$PILOT/template/hookify-block.local.md" "$RUN/repo/.claude/hookify.pr-rules.local.md"
      ;;
    Z)
      cp "$PILOT/template/settings-A.json" "$RUN/repo/.claude/settings.json"
      mkdir -p "$RUN/repo/.claude/rules"
      cp "$PILOT/template/rules-pr.md" "$RUN/repo/.claude/rules/pr-rules.md"
      ZIPTIE_HOOK="$(cd "$PILOT/.." && pwd)/hooks/pretooluse.py"
      python3 - "$RUN/repo/.claude/settings.json" "$ZIPTIE_HOOK" <<'PYEOF'
import json, sys
path, hook = sys.argv[1], sys.argv[2]
with open(path) as f:
    conf = json.load(f)
conf["hooks"] = {"PreToolUse": [{"matcher": "Bash", "hooks": [
    {"type": "command", "command": 'python3 "%s"' % hook, "timeout": 10}]}]}
with open(path, "w") as f:
    json.dump(conf, f, indent=2)
PYEOF
      ;;
    *)
      echo "알 수 없는 조건: $COND (A|B|AL|BL|HW|HB|Z)" >&2; exit 1
      ;;
  esac
  # B 계열이 아니면 JIT 훅 스크립트 제거 (settings에서 참조 안 함)
  case "$COND" in B|BL) ;; *) rm -f "$RUN/repo/.claude/hooks/inject.py" ;; esac

  # 롱컨텍스트(L) 조건: 로그 분석 선행 과제로 컨텍스트를 부풀린 뒤 PR 과제 수행
  RUN_TASK="$TASK"
  MAX_TURNS=25
  case "$COND" in *L) RUN_TASK="$LONG_TASK"; MAX_TURNS=50 ;; esac
  # 숏 조건에는 로그 파일이 불필요 (조건 간 유일한 차이를 과제로 한정)
  case "$COND" in *L) ;; *) rm -rf "$RUN/repo/data" ;; esac

  # 로컬 bare 리모트 — push가 네트워크 없이 성공하도록
  git init -q --bare "$RUN/remote.git"
  (
    cd "$RUN/repo" || exit 1
    git init -q -b main
    git add -A && git -c user.email=lab@test -c user.name=lab commit -qm "initial commit"
    git remote add origin "$RUN/remote.git"
    git push -q origin main
  )

  # 런 디렉토리를 신뢰 워크스페이스로 등록 (미등록 시 settings.json이 무시됨)
  python3 - "$RUN/repo" <<'PYEOF'
import json, os, sys
path = os.path.expanduser("~/.claude.json")
with open(path) as f:
    conf = json.load(f)
conf.setdefault("projects", {}).setdefault(sys.argv[1], {})["hasTrustDialogAccepted"] = True
with open(path, "w") as f:
    json.dump(conf, f, indent=2)
PYEOF

  echo "[$COND-$i] 시작 $(date +%H:%M:%S)"
  (
    cd "$RUN/repo" || exit 1
    PATH="$PILOT/mock-bin:$PATH" \
    GH_CAPTURE_DIR="$RUN/capture" \
    claude -p "$RUN_TASK" --model "$MODEL" --max-turns "$MAX_TURNS" \
      > "$RUN/out.log" 2>&1
  )
  N_CAPTURE=$(ls "$RUN/capture" 2>/dev/null | wc -l | tr -d ' ')
  echo "[$COND-$i] 종료 $(date +%H:%M:%S) — 캡처된 PR: $N_CAPTURE"
done
