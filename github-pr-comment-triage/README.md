# Endor Labs Triage Scripts

Two Python scripts that add interactive, comment-driven finding triage to your existing Endor Labs PR scan.

After the scan runs, `post_triage_comment.py` posts a numbered findings table to the PR. Developers reply with `/endor fp 1,2` or `/endor accept-risk 3` to triage findings without leaving the PR. `handle_triage_command.py` picks up those commands, creates ignore entries in `.endorignore.yaml`, commits them to the PR branch, and replies with a confirmation.

---

## Setup

### 1. Download the scripts

Copy the scripts from the [`scripts/`](scripts/) folder in this repo into your repository.

### 2. Add to your scan step

Call `post_triage_comment.py` right after your `endorctl scan` command:

```bash
endorctl scan \
  --enable-github-action-token \
  --pr \
  --pr-incremental \
  --enable-pr-comments \
  --scm-token=$GH_TOKEN \
  --scm-pr-id=$PR_NUMBER \
  --namespace=$ENDOR_NAMESPACE

python3 scripts/post_triage_comment.py
```

### 3. Add the triage handler

`handle_triage_command.py` needs something to trigger it when a developer posts an `/endor` comment. How you set that up depends on your CI system:

**GitHub Actions:** Copy [`templates/endor-triage.yml`](templates/endor-triage.yml) into `.github/workflows/` in your repo. It listens for `issue_comment` webhook events and calls `handle_triage_command.py` automatically — no extra infrastructure needed.

**Other CI systems (Jenkins, GitLab CI, CircleCI, etc.):** You will need to build your own webhook listener or event bridge that receives GitHub `issue_comment` events and triggers a CI job. That job should check out the PR branch and call `python3 scripts/handle_triage_command.py` with the environment variables listed in the reference below.

A sample end-to-end scan workflow is also available at [`templates/endor-scan.yml`](templates/endor-scan.yml).

---

## Triage commands

```
/endor fp 1,2
/endor accept-risk 3
/endor fp 1 --comment="Not reachable in prod" --expires=2026-12-31 --expire-if-fix
```

| Command | Effect |
|---------|--------|
| `/endor fp <numbers>` | Mark findings as **false positive** |
| `/endor accept-risk <numbers>` | Mark findings as **accepted risk** |

**Optional flags:**

| Flag | Description |
|------|-------------|
| `--comment="<text>"` | Note explaining the decision |
| `--expires=YYYY-MM-DD` | Auto-expire the ignore entry on this date |
| `--expire-if-fix` | Auto-expire when a fix becomes available |

---

## Environment variables

### GitHub Actions

When running in GitHub Actions, the scripts auto-detect everything from the environment. The only variables you need to set explicitly are:

| Variable | Script | How to set it |
|----------|--------|---------------|
| `GH_TOKEN` | both | `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` |
| `COMMENT_BODY` | `handle_triage_command.py` only | Auto-detected from the event payload — no action needed |

### Non-GitHub Actions CI

If you're running outside of GitHub Actions, set the following before calling each script:

**`post_triage_comment.py`**

```bash
export ENDOR_NAMESPACE=your-namespace   # same value passed to endorctl scan
export ENDOR_API_KEY=your-api-key       # Endor Labs auth
export GH_TOKEN=your-github-pat         # GitHub PAT with pull-requests:write
export REPO=owner/repo
export PR_NUMBER=123
```

**`handle_triage_command.py`**

```bash
export ENDOR_NAMESPACE=your-namespace
export ENDOR_API_KEY=your-api-key
export GH_TOKEN=your-github-pat         # GitHub PAT with pull-requests:write and contents:write
export REPO=owner/repo
export PR_NUMBER=123
export COMMENTER=github-username
export COMMENT_BODY="..."               # the full text of the /endor comment, extracted from
                                        # the GitHub issue_comment webhook payload at comment.body
```

You will also need the `gh` CLI installed on your runner and `git` configured with credentials to push to the repository.

---

## Requirements

- Python 3.10+
- `endorctl` on PATH (already installed for your scan step)
- `gh` CLI on PATH
- `git` configured on the runner
