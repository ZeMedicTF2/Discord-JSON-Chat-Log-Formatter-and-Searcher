import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DIVIDER = "-" * 40
MAX_LINES_LISTED_PER_FILE = 20  # prevent huge summaries; adjustable


@dataclass
class Attachment:
    filename: str
    ext: str
    proxy_url: str


@dataclass
class Message:
    timestamp: str
    date: str                      # YYYY-MM-DD derived from timestamp
    name: str
    content: Optional[str]
    attachments: List[Attachment]
    raw_block: str                 # original block text (for writing results)
    source_file: str               # file name from Chats folder
    start_line: int                # 1-based line number where header begins


def iter_txt_files(chats_dir: Path) -> List[Path]:
    return sorted([p for p in chats_dir.glob("*.txt") if p.is_file()])


def parse_header(line: str) -> Tuple[Optional[str], Optional[str]]:
    m = re.match(r"^\[(?P<ts>[^\]]+)\]\s+(?P<name>.+?)\s*$", line)
    if not m:
        return None, None
    return m.group("ts"), m.group("name")


def derive_date_from_timestamp(ts: str) -> str:
    if len(ts) >= 10 and ts[4] == "-" and ts[7] == "-":
        return ts[:10]
    return "NO_DATE"


def parse_block(block_lines: List[str], source_file: str, start_line: int) -> Optional["Message"]:
    while block_lines and block_lines[-1].strip() == "":
        block_lines.pop()

    if not block_lines:
        return None

    ts, name = parse_header(block_lines[0])
    if not ts or not name:
        return None

    date = derive_date_from_timestamp(ts)

    content_lines: List[str] = []
    attachments: List[Attachment] = []

    i = 1
    while i < len(block_lines):
        line = block_lines[i].rstrip("\n")

        if line.startswith("Attachment:"):
            filename = line[len("Attachment:"):].strip()
            proxy_url = ""

            if i + 1 < len(block_lines):
                nxt = block_lines[i + 1].rstrip("\n")
                if nxt.startswith("Proxy:"):
                    proxy_url = nxt[len("Proxy:"):].strip()
                    i += 1

            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            attachments.append(Attachment(filename=filename, ext=ext, proxy_url=proxy_url))
            i += 1
            continue

        if line.startswith("Proxy:"):
            i += 1
            continue

        if line.strip() != "":
            content_lines.append(line)
        i += 1

    content = "\n".join(content_lines).strip() if content_lines else None
    if content == "":
        content = None

    raw_block = "\n".join(block_lines).rstrip() + "\n" + DIVIDER + "\n"

    return Message(
        timestamp=ts,
        date=date,
        name=name,
        content=content,
        attachments=attachments,
        raw_block=raw_block,
        source_file=source_file,
        start_line=start_line,
    )


def parse_file_into_messages(fp: Path) -> List[Message]:
    lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()

    messages: List[Message] = []
    current_block: List[str] = []
    current_start_line: Optional[int] = None

    def flush_block() -> None:
        nonlocal current_block, current_start_line
        if current_block and current_start_line is not None:
            msg = parse_block(current_block, source_file=fp.name, start_line=current_start_line)
            if msg:
                messages.append(msg)
        current_block = []
        current_start_line = None

    for idx, line in enumerate(lines, start=1):
        if line.strip() == DIVIDER:
            flush_block()
            continue

        if current_start_line is None and line.strip() != "":
            current_start_line = idx

        current_block.append(line)

    flush_block()
    return messages


def load_all_messages(chats_dir: Path) -> List[Message]:
    all_msgs: List[Message] = []
    for fp in iter_txt_files(chats_dir):
        all_msgs.extend(parse_file_into_messages(fp))
    return all_msgs


def prompt_optional(prompt: str) -> Optional[str]:
    v = input(prompt).strip()
    return v if v else None


def prompt_optional_date() -> Optional[str]:
    raw = input("Date (d/m/y) or Enter for any: ").strip()
    if not raw:
        return None

    parts = re.split(r"[\/\-\.\s]+", raw)
    if len(parts) != 3:
        print("Invalid date format. Use d/m/y, e.g. 5/2/2026. Ignoring date filter.")
        return None

    try:
        d = int(parts[0])
        m = int(parts[1])
        y = int(parts[2])
    except ValueError:
        print("Date must be integers. Ignoring date filter.")
        return None

    if not (1 <= m <= 12 and 1 <= d <= 31 and 1 <= y <= 9999):
        print("Date values out of range. Ignoring date filter.")
        return None

    return f"{y:04d}-{m:02d}-{d:02d}"


def prompt_optional_bool(prompt: str) -> Optional[bool]:
    raw = input(prompt).strip().lower()
    if raw == "":
        return None
    if raw in ("y", "yes", "true", "t", "1"):
        return True
    if raw in ("n", "no", "false", "f", "0"):
        return False
    print("Please enter y, n, or press Enter for any.")
    return None


def compile_contains_pattern(user_input: str) -> Tuple[str, re.Pattern]:
    """
    Behavior:
      - If user types: "target" (surrounded by double quotes)
          -> exact token match, case-insensitive (rejects targets, atarget, ta rget)
      - Otherwise:
          -> substring match, case-insensitive (the old behavior)

    Note: this sacrifices searching for the literal quote character, as requested.
    """
    s = user_input.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        token = s[1:-1]
        escaped = re.escape(token)
        pat = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
        return user_input, pat

    escaped = re.escape(s)
    pat = re.compile(escaped, re.IGNORECASE)
    return user_input, pat


def matches_filters(msg: Message, filters: Dict[str, Any]) -> bool:
    date_filter: Optional[str] = filters.get("date")
    if date_filter is not None and msg.date != date_filter:
        return False

    name_filter: Optional[str] = filters.get("name")
    if name_filter is not None and msg.name.lower() != name_filter.lower():
        return False

    hay = msg.content or ""

    contains_pat: Optional[re.Pattern] = filters.get("contains_pat")
    if contains_pat is not None:
        if not contains_pat.search(hay):
            return False

    exclude_filter: Optional[str] = filters.get("exclude")
    if exclude_filter is not None:
        if exclude_filter.lower() in hay.lower():
            return False

    has_att_filter: Optional[bool] = filters.get("has_attachment")
    has_att = len(msg.attachments) > 0
    if has_att_filter is not None and has_att != has_att_filter:
        return False

    att_ext_filter: Optional[str] = filters.get("attachment_ext")
    if att_ext_filter is not None:
        if not has_att:
            return False
        want = att_ext_filter.lower().lstrip(".")
        if not any(a.ext == want for a in msg.attachments):
            return False

    return True


def format_filters_summary(filters: Dict[str, Any]) -> str:
    def show(v: Any) -> str:
        return "ANY" if v is None else str(v)

    return (
        "Search filters used:\n"
        f"- Date: {show(filters.get('date'))}\n"
        f"- Global name: {show(filters.get('name'))}\n"
        f"- Content contains: {show(filters.get('contains_raw'))}\n"
        f"- Exclude content: {show(filters.get('exclude'))}\n"
        f"- Has attachment: {show(filters.get('has_attachment'))}\n"
        f"- Attachment type/ext: {show(filters.get('attachment_ext'))}\n"
    )


def build_file_summary(matched: List[Message]) -> str:
    by_file: Dict[str, List[int]] = {}
    for m in matched:
        by_file.setdefault(m.source_file, []).append(m.start_line)

    lines: List[str] = ["Per-file summary:"]
    if not by_file:
        lines.append("(No matches.)")
        return "\n".join(lines) + "\n"

    items = sorted(by_file.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))
    for fname, line_nums in items:
        line_nums_sorted = sorted(line_nums)
        count = len(line_nums_sorted)

        if count <= MAX_LINES_LISTED_PER_FILE:
            nums_str = ", ".join(str(n) for n in line_nums_sorted)
            lines.append(f"Found {count} entries in {fname} on lines {nums_str}")
        else:
            shown = line_nums_sorted[:MAX_LINES_LISTED_PER_FILE]
            nums_str = ", ".join(str(n) for n in shown)
            remaining = count - MAX_LINES_LISTED_PER_FILE
            lines.append(
                f"Found {count} entries in {fname} on lines {nums_str}, ... (+{remaining} more)"
            )

    return "\n".join(lines) + "\n"


def strip_trailing_divider(raw_block: str) -> str:
    lines = raw_block.splitlines(keepends=True)

    while lines and lines[-1].strip() == "":
        lines.pop()

    if lines and lines[-1].strip() == DIVIDER:
        lines.pop()

    out = "".join(lines)
    if out and not out.endswith("\n"):
        out += "\n"
    return out


def compute_total_chars_for_output(matched: List[Message]) -> int:
    total = 0
    if not matched:
        return 0

    last_index_for_file: Dict[str, int] = {}
    for i, m in enumerate(matched):
        last_index_for_file[m.source_file] = i

    for i, m in enumerate(matched):
        is_last_in_file_group = (last_index_for_file.get(m.source_file) == i)
        block = strip_trailing_divider(m.raw_block) if is_last_in_file_group else m.raw_block
        total += len(block)
        total += 1  # extra blank line after each block
    return total


def write_matched_grouped_by_file(f, matched: List[Message]) -> None:
    if not matched:
        return

    last_index_for_file: Dict[str, int] = {}
    for i, m in enumerate(matched):
        last_index_for_file[m.source_file] = i

    current_file: Optional[str] = None
    for i, m in enumerate(matched):
        if current_file != m.source_file:
            current_file = m.source_file
            f.write("=" * 60 + "\n")
            f.write(f"{current_file}\n")
            f.write("=" * 60 + "\n\n")

        is_last_in_file_group = (last_index_for_file.get(m.source_file) == i)
        block = strip_trailing_divider(m.raw_block) if is_last_in_file_group else m.raw_block

        f.write(block)
        if not block.endswith("\n"):
            f.write("\n")
        f.write("\n")


def main() -> None:
    base = Path(__file__).parent
    chats_dir = base / "Chats"
    if not chats_dir.exists() or not chats_dir.is_dir():
        raise FileNotFoundError(f"Missing sibling folder 'Chats' at: {chats_dir}")

    out_path = base / "search_results.txt"

    print("=== Discord Chat Search ===")
    print("Leave any prompt blank to not filter by that field.\n")
    print('Tip: to match an EXACT word/token, wrap it in quotes, e.g. "target"\n')

    date_filter = prompt_optional_date()
    name_filter = prompt_optional("Global name (exact) or Enter for any: ")

    contains_raw_input = prompt_optional('Content contains (substring) OR "exact" token, or Enter for any: ')
    contains_raw: Optional[str] = None
    contains_pat: Optional[re.Pattern] = None
    if contains_raw_input:
        contains_raw, contains_pat = compile_contains_pattern(contains_raw_input)

    exclude_filter = prompt_optional("Exclude content (substring) or Enter for any: ")
    has_attachment_filter = prompt_optional_bool("Has attachment? (y/n) or Enter for any: ")

    attachment_ext_filter: Optional[str] = None
    if has_attachment_filter is True:
        attachment_ext_filter = prompt_optional(
            "Attachment type/ext (png/mp4/jpg/etc) or Enter for any: "
        )
        if attachment_ext_filter:
            attachment_ext_filter = attachment_ext_filter.lower().lstrip(".")

    filters: Dict[str, Any] = {
        "date": date_filter,
        "name": name_filter,
        "contains_raw": contains_raw,
        "contains_pat": contains_pat,
        "exclude": exclude_filter,
        "has_attachment": has_attachment_filter,
        "attachment_ext": attachment_ext_filter,
    }

    messages = load_all_messages(chats_dir)

    matched = [m for m in messages if matches_filters(m, filters)]
    matched.sort(key=lambda m: m.timestamp)

    total_entries = len(matched)
    total_chars = compute_total_chars_for_output(matched)

    with out_path.open("w", encoding="utf-8") as f:
        f.write(format_filters_summary(filters))
        f.write("\n")
        f.write(build_file_summary(matched))
        f.write(f"\nTotal {total_entries} entries, with {total_chars} characters.\n")
        f.write("\n")
        f.write("=" * 60 + "\n")
        f.write("Matched messages (sorted by timestamp):\n")
        f.write("=" * 60 + "\n\n")

        write_matched_grouped_by_file(f, matched)

    print("\n=== Done ===")
    print(f"Scanned files in: {chats_dir}")
    print(f"Total messages read: {len(messages)}")
    print(f"Matches: {len(matched)}")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
