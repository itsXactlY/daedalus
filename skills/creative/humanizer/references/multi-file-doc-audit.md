# Multi-file doc audit — pattern scan recipe

Companion to the "Multi-file project docs audit" section in `SKILL.md`. Copy-paste this when you need to scan a directory of .md files for the 29 AI patterns at once. Faster than reading each file end-to-end.

## The script

```python
import re
from daedalus_tools import read_file

files = [
    "/path/to/doc1.md",
    "/path/to/doc2.md",
    # ...
]

# AI tell patterns (compiled regex, case-insensitive)
patterns = {
    "P1_significance": r"\b(testament|underscor\w+|pivotal|crucial|enduring|tapestry|landscape|deeply rooted|stands as|serves as|setting the stage|key turning point|indelible mark|focal point|vital role|vibrant|evolving landscape)\b",
    "P3_-ing_tail":   r",\s+(showcas\w+|underscor\w+|emphasiz\w+|highlight\w+|reflect\w+|symboliz\w+|contribut\w+|foster\w+|cultivat\w+|encompass\w+|ensuring|leveraging)\w*\s",
    "P4_promo":       r"\b(blazing|seamless[,\s]+intuitive|nestled|breathtaking|groundbreaking|must-visit|renowned|profound|commitment to|empower\w+)\b",
    "P7_ai_vocab":    r"\b(delve|intricat\w+|interplay|tapestry|garner|valuable\b|key\s+(?:role|moment|insight|driver|component|aspect))\b",
    "P9_neg_par":     r"(?:not\s+(?:just|merely|only)\s+\w+[,;]?\s+(?:it|but)\s+is|it's\s+not\s+(?:just|merely|only)\s+about)",
    "P10_rule3":      r"\b\w+,\s+\w+,\s+and\s+\w+\b(?=\s+(?:in|of|to|for|that|which|ensure|with|by|when|on)\b)",
    "P14_em_dash":    r"—",
    "P15_bold_inline": r"\*\*[A-Z][^*\n]{1,40}:\*\*\s",
    "P16_inline_hdr": r"^\s*-\s*\*\*[^*]+:\*\*",
    "P19_curly":      r'[“”‘’]',
    "P20_collab":     r"\b(I hope this helps|Of course!|Certainly!|Would you like|let me know|here is a)\b",
    "P22_sycophant":  r"\b(Great question!|You're absolutely right|That's an excellent)\b",
    "P23_filler":     r"\b(In order to|At this point in time|Due to the fact that|In the event that|has the ability to|It is important to note)\b",
    "P24_hedging":    r"\b(could potentially|might possibly|could conceivably|may potentially)\b",
    "P25_positive_close": r"\b(exciting times|the future looks bright|journey toward excellence|major step in the right direction)\b",
    "P27_persuasive": r"\b(at its core|the real question is|what really matters|fundamentally|the deeper issue|the heart of the matter)\b",
    "P28_signpost":   r"\b(let's dive in|let's explore|let's break this down|here's what you need to know|now let's look|without further ado)\b",
    "P29_frag_hdr":   r"^##\s+\w+\s*\n\s*\n[A-Z][a-z]+\s+(?:is|are|matter)\s+\.",
}

for fpath in files:
    print(f"\n{'='*70}\n{fpath}\n{'='*70}")
    data = read_file(fpath, limit=2000)
    if "error" in data:
        print(f"ERROR: {data['error']}")
        continue
    text = data["content"]
    lines = text.splitlines()
    print(f"Lines: {len(lines)}  Size: {len(text)} chars\n")
    for pname, pat in patterns.items():
        hits = []
        for i, line in enumerate(lines, 1):
            for m in re.finditer(pat, line, re.IGNORECASE):
                hits.append((i, m.group(0)[:50], line.strip()[:90]))
                if len(hits) >= 3:
                    break
            if len(hits) >= 3:
                break
        if hits:
            print(f"[{pname}] {len(hits)}+ hits")
            for ln, mt, ctx in hits[:2]:
                print(f"  L{ln}: '{mt}' in: {ctx}")
            print()
```

## How to interpret the output

**Em-dashes (P14) will be the most-hit pattern in any technical doc.** That's normal. Don't treat it as "AI-generated" — see pitfalls in the main SKILL.md. The pattern scan is a STARTING POINT for human review, not a verdict.

**Pattern counts cluster.** If a single section has 5+ different patterns, that section is AI-generated and needs a full rewrite. If patterns are scattered 1-2 per file, the writer was human-leaning; spot-fix the worst hits.

**False positives are common** in technical docs that intentionally use:
- "Stand as", "key component", "tapestry" — actual technical terms
- Rule-of-three in protocol stacks (X3DH + Double Ratchet + AES-256-GCM)
- Em-dashes in bilingual formatting
- Bolded `**Fix for X**:` labels in troubleshooting

Read the matched lines in context before patching. A high P16 count in a troubleshooting manual is GOOD documentation, not AI slop.

## When to add custom patterns

If a scan reveals a pattern not in the 29 (e.g. brand-specific jargon, internal terminology used wrong), add it as `P30_custom_<name>` and re-scan. Don't just patch individual instances — add the pattern so future audits catch the same drift.

## After the scan

Once you have the per-file verdicts:

1. Read 100-200 lines from each file (intro + middle) to assess voice, specificity, and content quality.
2. Build a verdict table in your reply:

   | File | Lines | Verdict | Action |
   |---|---|---|---|
   | README.md | 415 | minor | patch intro (3 paragraphs) |
   | MANUAL.md | 85 | clean | none |
   | MANUAL_FOUNDATION.md | 174 | clean (style guide) | skip |
   | MANUAL_USER.md | 481 | clean | none |
   | MANUAL_ADMIN.md | 1031 | 1 stray ref | strip AC Infinity sentence |
   | MANUAL_TROUBLESHOOTING.md | 1053 | clean | none |

3. Apply targeted patches per class (humanizer / rebrand / stray) — separate commits.
4. Verify with re-scan + grep counts.

## Tooling notes

- `read_file` 100K char limit → for larger files, use `execute_code` and read the file directly with Python's `open()`, or split into chunks.
- `search_files(target='content', path=fpath, pattern=...)` is faster for single-pattern searches (uses ripgrep). Use the `execute_code` recipe only when you want to run ALL 29 patterns in one pass.
- `terminal` with `grep -cF "<pat>" path` is the fastest way to count exact-string matches across many files. Use it for the "verify" step after a bulk replacement.
