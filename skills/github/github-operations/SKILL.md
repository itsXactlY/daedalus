---
name: github-operations
description: "Complete GitHub workflow mastery: authentication, repositories, PRs, issues, code review, CI/CD, releases, and secrets. Covers gh CLI and git+curl fallback patterns."
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Git, Pull-Requests, Issues, Code-Review, CI/CD, Repositories, Authentication]
    related_skills: [hermes-agent, mcp]
---

# GitHub Operations — Complete Workflow Mastery

This umbrella skill consolidates all GitHub-related workflows into a single reference. Each section addresses a specific use case, from authentication to advanced CI/CD troubleshooting.

## Why This Skill Exists

GitHub work in Hermes flows through two fundamental patterns:
1. **`gh` CLI** — cleaner, richer, recommended when installed
2. **`git` + `curl` fallback** — works everywhere, no installation needed

This skill's reference files contain the exact commands, templates, and patterns used across sessions.

---

## 1. Authentication Setup

Trigger: Working with any GitHub repository, PR, issue, or API call.

### Quick Detection Pattern

```bash
# Run via terminal tool to detect auth method
if command -v gh &>/dev/null && gh auth status &>/dev/null 2>&1; then
  AUTH=gh
else
  AUTH=git
  # Extract token from various sources
  if [ -z "$GITHUB_TOKEN" ]; then
    if [ -f ~/.hermes/.env ] && grep -q "^GITHUB_TOKEN=" ~/.hermes/.env; then
      GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" ~/.hermes/.env | head -1 | cut -d= -f2 | tr -d '\n\r')
    elif [ -f ~/.git-credentials ] && grep -q "github.com" ~/.git-credentials 2>/dev/null; then
      GITHUB_TOKEN=$(grep "github.com" ~/.git-credentials | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|')
    fi
  fi
fi
```

### Auth Methods

| Method | When | Setup |
|--------|------|-------|
| **gh auth login** | Desktop with browser | `gh auth login` → GitHub.com → HTTPS → browser OAuth |
| **gh auth login --with-token** | Headless | `echo "TOKEN" \| gh auth login --with-token` |
| **Personal Access Token** | No gh installed | Create at https://github.com/settings/tokens → add `repo`, `workflow` scopes → `git config --global credential.helper store` → first git operation prompts for token |
| **SSH Key** | Prefer SSH | Generate: `ssh-keygen -t ed25519` → add `~/.ssh/id_ed25519.pub` to GitHub → `git config --global url."git@github.com:".insteadOf "https://github.com/"` |

---

## 2. Repository Management

### Clone Patterns
```bash
# Standard clone (HTTPS)
git clone https://github.com/owner/repo.git

# Shallow clone (faster for large repos)
git clone --depth 1 https://github.com/owner/repo.git

# Specific branch
git clone --branch develop https://github.com/owner/repo.git

# With gh
gh repo clone owner/repo
gh repo clone owner/repo -- --depth 1
```

### Create Repository
```bash
# With gh
gh repo create my-project --public --clone
gh repo create my-project --private --description "Description" --license MIT

# With curl (manual)
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user/repos \
  -d '{"name":"my-project","private":false}'
```

### Fork + Sync
```bash
gh repo fork owner/repo --clone
# Add upstream
git remote add upstream https://github.com/owner/repo.git
# Sync pattern
git fetch upstream && git checkout main && git merge upstream/main
```

---

## 3. Pull Request Workflow

### Pre-Flight: Check Fork vs Local Divergence (BEFORE creating the branch)

> **PITFALL — diverged local main on a forked repo.**
> `git checkout main && git pull origin main` is the standard recipe in
> plain-repo workflows, but on a **forked** repo it can silently lie:
> `origin` is usually the upstream (`NousResearch/hermes-agent`), but
> the PR target is your own `fork` remote. A stale local `main` plus an
> older `fork/main` means the diff between the branch you push and
> `fork/main` will swallow the entire fork's history. A real session
> shipped a PR with **+1,151,913 / -98,661** lines because of this.
> The user reaction was deserved: "branch -> fix -> PR! not with the
> _WHOLE DIPSHIT MESS_ attached!"

> **PITFALL — the fix is needed in two places when the fork diverges from upstream.**
> A real session shipped a "complete" fix to the fork, the user asked
> "compare against nous upstream too, and get a fix live if same 1:1
> crap exist there still!" — and they were right. The fork and upstream
> had diverged 6,481 commits, with **two completely different file
> paths** for the same code (`gateway/platforms/discord.py` on the
> fork vs `plugins/platforms/discord/adapter.py` on upstream). The
> fix in the fork was real but the user still saw noisy logs from
> the upstream code path because nothing was merged.
>
> **Workflow for any fork-and-upstream work:**
>
> ```bash
> # 1. After you fix the fork, fetch upstream main and compare code paths.
> git fetch origin main
> git diff --stat fork/main origin/main -- plugins/ gateway/
>
> # 2. If upstream has the same bug (which is likely on a diverged fork),
> #    base a NEW branch on origin/main and apply the fix there.
> git checkout -b fix/same-name origin/main
> # ... apply the same logical fix, adapted to the upstream file layout ...
> git push -u fork fix/same-name
>
> # 3. Open the upstream PR with --repo pointed at upstream.
> gh pr create --repo NousResearch/hermes-agent --base main \
>   --head itsXactlY:fix/same-name --title "..." --body "..."
>
> # 4. Link both PRs in each other's description so reviewers can see
> #    they're parallel.
> ```
>
> The user is going to ask "is the fix live upstream?" if the same bug
> exists there. Save the second round-trip by checking before they ask.

```bash
# 1. Discover the remotes and their branch heads.
git remote -v
git rev-parse main                  # local main tip
git rev-parse fork/main             # the remote you'll actually PR against
# (use origin/main or whatever remote name you push to — adapt the name)

# 2. Measure the divergence. A non-zero number here is the smoking gun.
git log --oneline main..fork/main | wc -l   # commits in fork not in local
git log --oneline fork/main..main | wc -l   # commits in local not in fork

# 3. Base the branch on the REMOTE ref, not local main. This is the
#    single command that prevents the 1.15M-line PR.
git checkout -b fix/short-name fork/main

# 4. Work, commit, then verify the diff stat BEFORE pushing. A real fix
#    branch should be <1000 lines / <10 files unless it's a refactor.
git diff --stat fork/main...HEAD
# If this is huge (thousands of files, hundreds of K of changes), you
# forgot step 3. Abort: git checkout main && git branch -D fix/short-name
```

See `references/fork-divergence-pitfall.md` for the full worked example
(commands, what failed, what the correct sequence looks like).

### Create Branch + Commit
```bash
git fetch origin
git checkout main && git pull origin main
git checkout -b feat/description

# Commit with conventional format
git add file1.py file2.py
git commit -m "feat: add new feature

- Detail 1
- Detail 2"
```

### Push + Create PR
```bash
git push -u origin HEAD

# With gh
gh pr create --title "..." --body "..." --reviewer user1

# With curl
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls \
  -d '{"title":"...","body":"...","head":"feat/description","base":"main"}'
```

### Monitor CI
```bash
# With gh
gh pr checks
gh pr checks --watch

# With curl (poll loop)
SHA=$(git rev-parse HEAD)
for i in $(seq 1 20); do
  STATUS=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
    https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/status \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")
  [ "$STATUS" = "success" ] || [ "$STATUS" = "failure" ] && break
  sleep 30
done
```

### Merge
```bash
gh pr merge --squash --delete-branch
gh pr merge --auto --squash --delete-branch
```

---

## 4. Code Review

### Review Local Changes
```bash
git diff --staged
git diff main...HEAD --stat
git diff main...HEAD --name-only
```

### Common Issue Checks
```bash
# Debug statements
git diff main...HEAD | grep -n "print(\|console.log\|TODO\|FIXME"

# Secrets
git diff main...HEAD | grep -in "password\|secret\|api_key\|token.*="

# Merge conflict markers
git diff main...HEAD | grep -n "<<<<<<\|>>>>>>\|======"
```

### Review Output Structure
```markdown
## Code Review Summary

### Critical
- **file.py:45** — SQL injection: use parameterized queries.

### Warnings
- **models/user.py:23** — Password not hashed.

### Suggestions
- **utils/helpers.py:8** — Duplicates logic in core/utils.py.

### Looks Good
- Clean separation of concerns in middleware.
```

### Inline PR Comments
```bash
# Get head commit SHA
HEAD_SHA=$(gh pr view 123 --json headRefOid --jq '.headRefOid')

gh api repos/$OWNER/$REPO/pulls/123/comments \
  --method POST -f body="Comment" -f path="file.py" \
  -f commit_id="$HEAD_SHA" -f line=45 -f side="RIGHT"
```

---

## 5. Issue Management

### List Issues
```bash
gh issue list
gh issue list --state open --label "bug"
gh issue list --assignee @me

# With curl
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/issues?state=open"
```

### Create Issue
```bash
gh issue create --title "..." --body "..." --label "bug" --assignee username

# With curl
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues \
  -d '{"title":"...","body":"...","labels":["bug"]}'
```

### Manage Issues
```bash
gh issue edit 42 --add-label "priority:high"
gh issue edit 42 --add-assignee @me
gh issue close 42
gh issue comment 42 --body "Investigating..."
```

---

## 6. Secrets & Releases

### Secrets (HTTP API - requires encryption)
```bash
# With gh (recommended)
gh secret set API_KEY --body "value"
gh secret list
gh secret delete API_KEY

# With curl - must encrypt first (see references/github-api-cheatsheet.md)
```

### Releases
```bash
gh release create v1.0.0 --generate-notes
gh release list
gh release download v1.0.0 --dir ./downloads

# With curl
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/releases \
  -d '{"tag_name":"v1.0.0","generate_release_notes":true}'
```

### GitHub Actions
```bash
gh workflow list
gh run list --limit 10
gh run view <RUN_ID> --log-failed
gh workflow run ci.yml --ref main
```

---

## 7. MCP Server Integration (Alternative to curl)

For programmatic GitHub work, configure the official MCP server in `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_..."
```

This provides tools like `mcp_github_list_issues`, `mcp_github_create_pull_request`, etc.

---

## Reference Files

- `references/review-output-template.md` — PR comment templates
- `references/ci-troubleshooting.md` — CI failure diagnosis patterns
- `references/conventional-commits.md` — Commit message format
- `references/github-api-cheatsheet.md` — API endpoint quick reference
- `references/fork-divergence-pitfall.md` — **When the PR diff is 1.15M lines, you forgot `git checkout -b branch fork/main`. Diagnosis + recovery recipe.**
- `references/parallel-pr-fork-and-upstream.md` — **When the fork is diverged from upstream, the same bug lives in both code paths. Workflow for shipping parallel PRs (itsXactlY fork + NousResearch upstream).** Also covers cherry-pick modify/delete failure modes and the "PREPARE but don't open" review-gate pattern.
- `templates/pr-body-bugfix.md` — Bug fix PR template
- `templates/bug-report.md` — Issue template
- `templates/feature-request.md` — Feature request template
- `scripts/gh-env.sh` — Auth detection helper script