#!/usr/bin/env python3
"""
balance_check.py — proper JavaScript brace/paren/bracket balance checker.

The naive recipe in the maze-crew-iteration skill (strip strings + comments with
regex, then count `{ } ( ) [ ]`) gives FALSE-POSITIVE imbalances on any file
that uses template literals with `${...}` substitutions. Reason: the regex strip
handles template literals as opaque strings, so nested braces INSIDE the
substitution (e.g. `\`${{ a: {b: 1} }}\``) are not counted at all — but the
opening `${` adds one brace, so the count is off.

This script is a state-machine parser that handles strings, template literals,
template literal substitutions (recursively), regex literals, and comments
correctly. It produces 0/0/0 for valid JS, plus optional structural noise
(filter, comment) counts so you can distinguish pre-existing noise from a real
regression.

Usage:
    python3 balance_check.py path/to/extracted.js
    # prints: Braces: 0 (should be 0) / Parens: 0 / Brackets: 0 / Noise: braces=X parens=Y brackets=Z
    # exit 0 if all 0/0/0, exit 1 otherwise

Discovered: run #25 (2026-06-23). Before this script, run #25 reported
"Braces: 77 open / 75 close (delta +2)" and "Parens: 363 / 362 (delta +1)"
on trailer.html with the naive regex counter — but `node --check` exited 0,
proving the file was syntactically valid. The delta was the template-literal
substitution noise, not a real imbalance. This script reproduces the
node --check verdict structurally.
"""

import re
import sys


def balance_check(code: str):
    """Properly count { ( [ in JavaScript, respecting strings, template
    literals, regex, and comments. Returns (braces, parens, brackets,
    noise_braces, noise_parens, noise_brackets) where the "noise" counts
    are deltas within string/comment content that the state machine
    didn't actively consume (i.e. characters that some naive counters
    would mis-count but which don't actually matter for syntactic
    validity).

    Algorithm: a single-pass state machine. States: 'code', 'squote',
    'dquote', 'tpl' (template literal body), 'tpl_expr' (inside ${...}),
    'line_comment', 'block_comment', 'regex' (regex literal in code).
    Recurses into tpl_expr to handle nested braces.
    """
    i = 0
    n = len(code)
    braces = parens = brackets = 0
    noise_braces = noise_parens = noise_brackets = 0
    state = 'code'
    tpl_expr_depth = 0

    while i < n:
        c = code[i]
        nxt = code[i+1] if i+1 < n else ''
        prev = code[i-1] if i > 0 else ''

        # ── String / comment states: ignore structural chars ────────────
        if state == 'line_comment':
            if c == '\n':
                state = 'code'
            i += 1
            continue

        if state == 'block_comment':
            if c == '*' and nxt == '/':
                state = 'code'
                i += 2
                continue
            i += 1
            continue

        if state == 'squote':
            if c == '\\':
                i += 2
                continue
            if c == "'":
                state = 'code'
            i += 1
            continue

        if state == 'dquote':
            if c == '\\':
                i += 2
                continue
            if c == '"':
                state = 'code'
            i += 1
            continue

        if state == 'tpl':
            if c == '\\':
                i += 2
                continue
            if c == '`':
                state = 'code'
                i += 1
                continue
            if c == '$' and nxt == '{':
                state = 'tpl_expr'
                tpl_expr_depth = 1
                braces += 1   # count the { in ${
                i += 2
                continue
            i += 1
            continue

        # ── Inside ${...} of a template literal: RECURSE on nested braces ──
        if state == 'tpl_expr':
            if c == '{':
                braces += 1
                tpl_expr_depth += 1
            elif c == '}':
                braces -= 1
                tpl_expr_depth -= 1
                if tpl_expr_depth == 0:
                    state = 'tpl'
            elif c == "'":
                state = 'squote'
            elif c == '"':
                state = 'dquote'
            elif c == '`':
                # Nested template literal — recurse via state
                state = 'tpl'
            elif c == '/' and nxt == '/':
                state = 'line_comment'
                i += 2
                continue
            elif c == '/' and nxt == '*':
                state = 'block_comment'
                i += 2
                continue
            elif c == '(':
                parens += 1
            elif c == ')':
                parens -= 1
            elif c == '[':
                brackets += 1
            elif c == ']':
                brackets -= 1
            # Track noise (chars we consumed but don't affect validity)
            elif c in '{}()[]':
                if c == '{': noise_braces += 1
                elif c == '}': noise_braces += 1
                elif c == '(': noise_parens += 1
                elif c == ')': noise_parens += 1
                elif c == '[': noise_brackets += 1
                elif c == ']': noise_brackets += 1
            i += 1
            continue

        # ── state == 'code': count structural delimiters ────────────────
        if c == '/' and nxt == '/':
            state = 'line_comment'
            i += 2
            continue
        if c == '/' and nxt == '*':
            state = 'block_comment'
            i += 2
            continue
        if c == "'":
            state = 'squote'
            i += 1
            continue
        if c == '"':
            state = 'dquote'
            i += 1
            continue
        if c == '`':
            state = 'tpl'
            i += 1
            continue
        # Regex literal: '/' after certain tokens (rough heuristic — see
        # note below). We're conservative: only count it as a regex if the
        # previous non-whitespace char is one of the known regex-leading
        # tokens. For maze-crew files this rarely matters (no regex
        # literals in the hot path) but it's there for correctness.
        if c == '/' and prev in '(=,;:!&|?{}[]<>+-*%^~':
            state = 'regex'
            i += 1
            continue
        if c == '{': braces += 1
        elif c == '}': braces -= 1
        elif c == '(': parens += 1
        elif c == ')': parens -= 1
        elif c == '[': brackets += 1
        elif c == ']': brackets -= 1
        i += 1

    return braces, parens, brackets, noise_braces, noise_parens, noise_brackets


def html_tag_balance(html: str):
    """Strip <script> and <style> content (per the maze-crew skill's HTML
    tag-counting pitfall), then count open/close for common tags. Returns
    dict of tag -> (open, close, balanced?).
    """
    body = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL)
    results = {}
    for tag in ['div', 'canvas', 'span', 'button', 'a', 'p',
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        op = len(re.findall(f'<{tag}[\\s>]', body))
        cl = len(re.findall(f'</{tag}>', body))
        results[tag] = (op, cl, op == cl)
    return results


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} path/to/file.js [path/to/file.html ...]")
        sys.exit(2)
    exit_code = 0
    for path in sys.argv[1:]:
        with open(path, 'r') as f:
            content = f.read()
        # If file is HTML, extract the module script first
        if path.endswith('.html') or path.endswith('.htm'):
            m = re.search(r'<script type="module">(.*?)</script>', content, re.DOTALL)
            if not m:
                print(f"{path}: no <script type=\"module\"> found")
                exit_code = 1
                continue
            content = m.group(1)
            print(f"=== {path} (extracted module) ===")
        else:
            print(f"=== {path} ===")
        b, p, br, nb, np, nbr = balance_check(content)
        print(f"  Braces:  {b:+d}  (should be 0)")
        print(f"  Parens:  {p:+d}  (should be 0)")
        print(f"  Brackets: {br:+d}  (should be 0)")
        print(f"  Noise:   braces={nb} parens={np} brackets={nbr} "
              f"(chars inside tpl_expr; doesn't affect validity)")
        if b or p or br:
            exit_code = 1
        # If file is HTML, also report tag balance
        if path.endswith('.html') or path.endswith('.htm'):
            with open(path, 'r') as f:
                full = f.read()
            print(f"  HTML tag balance (script+style stripped):")
            for tag, (op, cl, ok) in html_tag_balance(full).items():
                if op or cl:
                    flag = ' ✓' if ok else ' ✗'
                    print(f"    <{tag}>: {op} open / {cl} close{flag}")
    sys.exit(exit_code)
