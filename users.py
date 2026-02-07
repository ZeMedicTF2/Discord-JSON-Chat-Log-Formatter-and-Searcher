import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

FILE_HEADER_LINE = "=" * 60
ENTRY_DIVIDER = "-" * 5  # "-----"

# Toggle this to enable/disable name replacements
ENABLE_NAME_REPLACEMENTS = True

# Exact-match replacements (adjustable)
NAME_REPLACEMENTS = {
    "𓄧": "wnki",  # U+13127
    # "X": "x",
    # "Y": "y",
}


@dataclass
class UserInfo:
    global_name: str
    username: str
    user_id: str


def safe_str(x: Any) -> str:
    return str(x) if x is not None else ""


def normalize_name(name: str) -> str:
    if not ENABLE_NAME_REPLACEMENTS:
        return name
    return NAME_REPLACEMENTS.get(name, name)


def extract_author_fields(msg: Dict[str, Any]) -> Optional[UserInfo]:
    author = msg.get("author")
    if not isinstance(author, dict):
        return None

    user_id = author.get("id")
    username = author.get("username")
    global_name = author.get("global_name") or username

    if user_id is None and username is None and global_name is None:
        return None

    g = normalize_name(safe_str(global_name) if global_name is not None else "Unknown")
    u = safe_str(username) if username is not None else "Unknown"
    i = safe_str(user_id) if user_id is not None else "Unknown"

    return UserInfo(global_name=g, username=u, user_id=i)


def load_json_messages(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def main() -> None:
    base = Path(__file__).parent
    input_dir = base / "Input"
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Missing sibling folder 'Input' at: {input_dir}")

    json_files = sorted([p for p in input_dir.glob("*.json") if p.is_file()])
    if not json_files:
        raise FileNotFoundError(f"No .json files found in: {input_dir}")

    # Totals across all files: key by user_id if possible, else by (global_name, username)
    total_counts: Dict[str, int] = {}
    total_userinfo: Dict[str, UserInfo] = {}

    # Per file: filename -> key -> count
    per_file_counts: Dict[str, Dict[str, int]] = {}

    def make_key(ui: UserInfo) -> str:
        # Prefer stable ID as key
        if ui.user_id not in ("Unknown", ""):
            return f"id:{ui.user_id}"
        # fallback (less stable)
        return f"name:{ui.global_name}|user:{ui.username}"

    for jf in json_files:
        msgs = load_json_messages(jf)
        file_counts: Dict[str, int] = {}

        for m in msgs:
            ui = extract_author_fields(m)
            if ui is None:
                continue

            key = make_key(ui)

            file_counts[key] = file_counts.get(key, 0) + 1

            total_counts[key] = total_counts.get(key, 0) + 1
            total_userinfo.setdefault(key, ui)

        # Show as corresponding Chats file name (same stem)
        per_file_counts[jf.stem + ".txt"] = file_counts

    out_path = base / "users.txt"

    # Sort totals by count desc, then global_name
    total_sorted = sorted(
        total_counts.items(),
        key=lambda kv: (
            -kv[1],
            total_userinfo.get(kv[0], UserInfo("Unknown", "Unknown", "Unknown")).global_name.lower(),
        ),
    )

    with out_path.open("w", encoding="utf-8") as f:
        f.write("Unique users:\n")
        for key, cnt in total_sorted:
            ui = total_userinfo[key]
            f.write(f"{ui.global_name}, total entries {cnt}, username {ui.username}, ID {ui.user_id}\n")

        f.write("\n")

        for filename in sorted(per_file_counts.keys(), key=lambda x: x.lower()):
            f.write(FILE_HEADER_LINE + "\n")
            f.write(f"{filename}\n")
            f.write(FILE_HEADER_LINE + "\n")

            file_counts = per_file_counts[filename]
            if not file_counts:
                f.write("(No users found in this file.)\n\n")
                continue

            # Sort by entries in file desc, then global_name
            file_sorted = sorted(
                file_counts.items(),
                key=lambda kv: (
                    -kv[1],
                    total_userinfo.get(kv[0], UserInfo("Unknown", "Unknown", "Unknown")).global_name.lower(),
                ),
            )

            for idx, (key, cnt_in_file) in enumerate(file_sorted):
                ui = total_userinfo.get(key, UserInfo("Unknown", "Unknown", "Unknown"))
                f.write(f"{ui.global_name}\n")
                f.write(f"Entries in this file: {cnt_in_file}\n")

                if idx != len(file_sorted) - 1:
                    f.write(ENTRY_DIVIDER + "\n")

            f.write("\n")

    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
