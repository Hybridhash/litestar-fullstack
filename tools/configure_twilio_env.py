from __future__ import annotations

import sys
from getpass import getpass
from pathlib import Path

TWILIO_FIELDS: tuple[tuple[str, str, bool, bool], ...] = (
    ("TWILIO_ACCOUNT_SID", "", False, True),
    ("TWILIO_AUTH_TOKEN", "", True, True),
    ("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886", False, False),
)


def parse_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def prompt_value(key: str, current: str, secret: bool, default: str, hide_current: bool) -> str:
    effective_default = current or default
    if secret:
        if effective_default:
            prompt = f"{key} [press Enter to keep existing]: "
        else:
            prompt = f"{key}: "
        value = getpass(prompt)
        return value or current

    if hide_current and current:
        suffix = " [press Enter to keep existing]"
    else:
        suffix = f" [{effective_default}]" if effective_default else ""
    value = input(f"{key}{suffix}: ").strip()
    return value or effective_default


def render_env(existing_lines: list[str], updates: dict[str, str]) -> list[str]:
    rendered: list[str] = []
    seen: set[str] = set()
    for line in existing_lines:
        if "=" not in line or line.lstrip().startswith("#"):
            rendered.append(line)
            continue
        key, _ = line.split("=", 1)
        normalized_key = key.strip()
        if normalized_key in updates:
            rendered.append(f"{normalized_key}={updates[normalized_key]}")
            seen.add(normalized_key)
        else:
            rendered.append(line)

    missing = [key for key in updates if key not in seen]
    if missing:
        if rendered and rendered[-1].strip():
            rendered.append("")
        rendered.append("# Twilio (OTP verification)")
        for key in missing:
            rendered.append(f"{key}={updates[key]}")
    return rendered


def main() -> int:
    env_arg = sys.argv[1] if len(sys.argv) > 1 else ".env"
    env_path = Path(env_arg)
    existing_values = parse_env_file(env_path)
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    print(f"Configuring Twilio settings in {env_path}")
    print("For local OTP testing, use a real Auth Token. The placeholder '[AuthToken]' will not work.")

    updates: dict[str, str] = {}
    for key, default, secret, hide_current in TWILIO_FIELDS:
        current = existing_values.get(key, "")
        updates[key] = prompt_value(key, current, secret, default, hide_current)
    rendered = render_env(existing_lines, updates)
    env_path.write_text("\n".join(rendered) + "\n", encoding="utf-8")
    print(f"Updated {env_path}")
    print("Restart the app server after changing Twilio settings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
