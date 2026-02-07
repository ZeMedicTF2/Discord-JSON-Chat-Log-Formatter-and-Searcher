# Architecture

This project turns Discord-export JSON logs into readable transcripts, then provides searching and user summaries.

---

## Data flow

```text
Input/.json ──(parser.py)──> Chats/.txt ──(searcher.py)──> search_results.txt
│
└──────────────(users.py reads JSON directly)────────────> users.txt
```

---

## Why users.py reads JSON (not TXT)

The transcript format intentionally stays minimal for readability:
- timestamp
- global name
- content (optional)
- attachment filename + proxy_url (optional)

It does **not** include the user’s `id` or `username`.

Those exist in the original JSON (`author.id`, `author.username`), so `users.py` reads `Input/*.json` directly to reliably output:
- global name (display)
- username
- id
- totals and per-file counts

---

## Formats

### Input JSON
Each `Input/<file>.json` is expected to be a JSON array:

```text
[
{ Message },
{ Message },
...
]
```


A message typically contains:
- `timestamp` (ISO 8601 / RFC3339)
- `content` (string, may be empty)
- `attachments` (array)
- `author` (object: id, username, global_name, ...)
- optional reply fields like `referenced_message`

---

### Transcript TXT format (Chats/*.txt)

Each message becomes a block:

```text
[<timestamp>] <GlobalName>
<content> (optional)
Attachment: <filename> (optional; repeated)
Proxy: <proxy_url> (optional; repeated)
```

- The divider line is always:
  `----------------------------------------`
- This divider is used by `searcher.py` to split the transcript back into message blocks.

---

## Ordering

`parser.py` sorts messages **chronologically** (oldest → newest) by `timestamp`.

---

## Search rules (searcher.py)

### Sort
Matched results are sorted by `timestamp` (ISO strings sort correctly).

### Content contains
- Unquoted input (e.g. `target`) -> substring match (case-insensitive)
- Quoted input (e.g. `"target"`) -> exact token match (case-insensitive)
  - matches only when not adjacent to word characters

### Grouped output
`search_results.txt` prints a file header before messages from each transcript file.  
The last printed message per file group has its trailing divider removed for cleaner output.
