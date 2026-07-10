"""ziptie 룰 파일 로더 — .claude/rules/*.md (frontmatter + body)."""

import glob
import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass
class Rule:
    name: str
    tool: str
    pattern: str
    source: Optional[str]
    strength: str
    enabled: bool
    body: str
    path: str


def _parse_frontmatter(text: str):
    """우리 포맷 전용 미니 파서. key: value + 2칸 들여쓴 서브키 1단계만 지원."""
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    meta, body = {}, parts[2].strip()
    current_parent = None
    for line in parts[1].splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if ":" not in line:
            return None, body  # 포맷 위반 → 파싱 실패로 취급
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if indent == 0:
            if value == "":
                current_parent = key
                meta[key] = {}
            else:
                current_parent = None
                meta[key] = value
        else:
            if current_parent is None or not isinstance(meta.get(current_parent), dict):
                return None, body
            meta[current_parent][key] = value
    return meta, body


def parse_rule_file(path: str, quiet: bool = False) -> Optional[Rule]:
    """룰 파일 하나를 파싱한다. 어떤 실패든 None (예외를 밖으로 내지 않는다).

    quiet=True면 stderr 경고를 억제한다 (반환값은 동일).
    """
    try:
        with open(path, encoding="utf-8") as f:
            meta, body = _parse_frontmatter(f.read())
        if not meta:
            return None
        trigger = meta.get("trigger", {})
        name, tool, pattern = (
            meta.get("name"),
            trigger.get("tool"),
            trigger.get("pattern"),
        )
        if not (name and tool and pattern):
            return None
        if not _NAME_RE.match(name):
            if not quiet:
                print(
                    f"ziptie: rule {path}: invalid name '{name}' — [a-z0-9-]만 허용",
                    file=sys.stderr,
                )
            return None
        strength = meta.get("strength", "require-read")
        if strength not in ("require-read", "block", "inject"):
            if not quiet:
                print(
                    f"ziptie: rule {name}: unsupported strength '{strength}' — "
                    "require-read로 폴백",
                    file=sys.stderr,
                )
            strength = "require-read"
        enabled_raw = str(meta.get("enabled", "true"))
        enabled_lower = enabled_raw.lower()
        if enabled_lower not in ("true", "false"):
            if not quiet:
                print(
                    f"ziptie: rule {name}: unrecognized enabled value "
                    f"'{enabled_raw}' — true로 취급",
                    file=sys.stderr,
                )
            enabled = True
        else:
            enabled = enabled_lower == "true"
        return Rule(
            name=name,
            tool=tool,
            pattern=pattern,
            source=meta.get("source") or None,
            strength=strength,
            enabled=enabled,
            body=body,
            path=path,
        )
    except Exception as e:  # 안전 기본값: 절대 세션을 죽이지 않는다
        if not quiet:
            print(f"ziptie: rule parse error {path}: {e}", file=sys.stderr)
        return None


def load_rules(project_dir: str, quiet: bool = False) -> List[Rule]:
    rules = []
    for path in sorted(
        glob.glob(os.path.join(project_dir, ".claude", "rules", "*.md"))
    ):
        rule = parse_rule_file(path, quiet=quiet)
        if rule and rule.enabled:
            rules.append(rule)
    return rules
