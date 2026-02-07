import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DIVIDER = "-" * 40

# Toggle this to enable/disable name replacements
ENABLE_NAME_REPLACEMENTS = True

# Exact-match replacements (adjustable)
NAME_REPLACEMENTS = {
    "𓄧": "wnki",  # U+13127
    # "X": "x",
    # "Y": "y",
}


def normalize_name(name: str) -> str:
    if not ENABLE_NAME_REPLACEMENTS:
        return name
    return NAME_REPLACEMENTS.get(name, name)


def get_global_name(msg: Dict[str, Any]) -> str:
    author = msg.get("author") or {}
    name = author.get("global_name") or author.get("username") or "Unknown"
    return normalize_name(str(name))


def norm_text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    t = value.strip()
    return t if t else None


def extract_attachments(msg: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Keep only (filename, proxy_url) from msg["attachments"] when both exist.
    """
    out: List[Tuple[str, str]] = []
    atts = msg.get("attachments")
    if not isinstance(atts, list):
        return out

    for att in atts:
        if not isinstance(att, dict):
            continue
        filename = att.get("filename")
        proxy_url = att.get("proxy_url")
        if filename and proxy_url:
            out.append((str(filename), str(proxy_url)))
    return out


def format_message(msg: Dict[str, Any]) -> str:
    timestamp = msg.get("timestamp") or "NO_TIMESTAMP"
    name = get_global_name(msg)
    content = norm_text(msg.get("content"))

    lines: List[str] = [f"[{timestamp}] {name}"]

    if content is not None:
        lines.append(content)

    for filename, proxy_url in extract_attachments(msg):
        lines.append(f"Attachment: {filename}")
        lines.append(f"Proxy: {proxy_url}")

    lines.append(DIVIDER)
    return "\n".join(lines)


def sort_messages_chronological(data: List[Any]) -> List[Dict[str, Any]]:
    """
    Sort ascending by timestamp (oldest first). ISO8601 strings sort correctly.
    Messages without timestamps go last.
    """
    msgs = [x for x in data if isinstance(x, dict)]

    def key(m: Dict[str, Any]) -> Tuple[int, str]:
        ts = m.get("timestamp")
        if isinstance(ts, str) and ts:
            return (0, ts)
        return (1, "9999-99-99T99:99:99.999999+99:99")

    msgs.sort(key=key)
    return msgs


def parse_one_file(input_path: Path, output_path: Path) -> Tuple[int, int]:
    """
    Returns: (total_items_in_json, messages_written)
    """
    raw = input_path.read_text(encoding="utf-8", errors="replace")
    data = json.loads(raw)

    if not isinstance(data, list):
        raise ValueError(
            f"{input_path.name}: expected top-level JSON list, got {type(data).__name__}"
        )

    msgs = sort_messages_chronological(data)

    kept = 0
    with output_path.open("w", encoding="utf-8") as f:
        for item in msgs:
            f.write(format_message(item))
            f.write("\n")
            kept += 1

    return len(data), kept


def main() -> None:
    base = Path(__file__).parent
    input_dir = base / "Input"
    chats_dir = base / "Chats"

    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Missing sibling folder 'Input' at: {input_dir}")

    chats_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted([p for p in input_dir.glob("*.json") if p.is_file()])
    if not json_files:
        raise FileNotFoundError(f"No .json files found in: {input_dir}")

    total_files = 0
    total_msgs_written = 0

    for jp in json_files:
        out_name = jp.stem + ".txt"
        out_path = chats_dir / out_name  # overwrite if exists

        total_items, kept = parse_one_file(jp, out_path)
        total_files += 1
        total_msgs_written += kept

        print(f"{jp.name} -> Chats/{out_name} (json items: {total_items}, written: {kept})")

    print("\nDone.")
    print(f"Files processed: {total_files}")
    print(f"Total messages written: {total_msgs_written}")


if __name__ == "__main__":
    main()
