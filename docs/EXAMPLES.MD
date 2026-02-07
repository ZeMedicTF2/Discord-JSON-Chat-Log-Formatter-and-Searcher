# Examples

## Parsing example

### Input
`Input/myfile.json`

### Run

```text
python parser.py
```

### Output

`Chats/myfile.txt`

---

## Searching examples

### Run

```text
python searcher.py
```
#### Example 1: date + user

- Date: 2/2/2026
- Global name: Medic
- Content contains: (blank)
- Exclude content: (blank)
- Has attachment: (blank)
This writes matches to search_results.txt.

#### Example 2: substring content search

- Content contains: `target`
Matches any message containing target in any casing, including inside other words.

#### Example 3: exact content search

- Content contains: `"target"`
Matches:

```text
• target
• TARGET
• TaRgEt
```

Rejects:

```text
• targets
• atarget
• ta rget
• TaRGe T
```

### Output

`./search_results.txt`

#### search_results.txt layout (simplified)

- filters used
- per-file summary (counts + line numbers)
- totals line
- grouped matched messages:
```md
============================================================
myfile.txt
============================================================

[... message block ...]

============================================================
otherfile.txt
============================================================

[... message block ...]
```

---

## User report examples

### Run

```text
python users.py
```

#### users.txt top summary (example)

```text
Unique users:
Medic, total entries 123, username ZeMedicTF2, ID 1234567890
Bob, total entries 99, username bobthebuilder, ID 1111111111
```

#### users.txt per-file breakdown (example)

```text
============================================================
myfile.txt
============================================================
Medic
Entries in this file: 30
-----
bob
Entries in this file: 12
```
