# Twice-Daily Collection, Once-Daily Publish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the AISStream data-collection pipeline twice a day (12h apart) while the live site keeps refreshing only once a day, in the morning.

**Architecture:** Add a second `cron` to the existing `nightly-update.yml` workflow 12 hours after the current one. Both runs execute the identical collection job; two steps branch on `github.event.schedule` so the new 18:00 AEST run commits its data with `[skip ci]` (lands on `main`, does not rebuild the site) while the existing 06:00 AEST run and manual dispatches commit normally and deploy. No pipeline or collector changes — coverage accumulates through the already-persisted state files.

**Tech Stack:** GitHub Actions (YAML workflow), `gh` CLI, Python pipeline (unchanged). Local YAML validation via a throwaway `pyyaml` install in the repo `.venv`.

**Spec:** `docs/superpowers/specs/2026-06-10-twice-daily-collection-design.md`

---

## Background the implementer needs

- **Only file touched:** `.github/workflows/nightly-update.yml`. Do **not** modify `deploy.yml`, anything under `pipeline/`, or `COLLECTION_DURATION`.
- **How the site deploys:** `deploy.yml` triggers on **any push to `main`** (`on: push: branches: [main]`) *and* via the explicit `gh workflow run deploy.yml` step at the end of this workflow. To stop the collect-only run from publishing we must defeat **both** paths:
  - The push path is defeated by putting `[skip ci]` in the data commit message. GitHub Actions skips `push`/`pull_request`-triggered workflow runs when the head commit message contains `[skip ci]` (also `[ci skip]`, `[no ci]`, `[skip actions]`). The `[skip ci]` only suppresses the *deploy*; this workflow is `schedule`/`workflow_dispatch`-triggered, not `push`, so it is unaffected.
  - The explicit path is defeated by gating the `Trigger Pages deploy` step with an `if:` condition.
- **`github.event.schedule`** holds the exact cron string that fired a scheduled run (e.g. `0 8 * * *`). For a `workflow_dispatch` run it is empty/undefined, so any `!=` comparison against a cron string is **true** for manual runs — manual runs therefore publish, preserving today's "publish now" behaviour.
- **Why no double-counting** (already verified against the pipeline): arrivals dedupe, `monthly-estimates` is rebuilt from `arrivals.json` each run, daily/en-route are last-write-wins snapshots. A second run only folds in more observations. (Full reasoning in the spec.)
- **DST:** `0 20 * * *` and `0 8 * * *` are exactly 12h apart in UTC, so the gap is stable across Australian DST. 20:00 UTC = 06:00 AEST / 07:00 AEDT. 08:00 UTC = 18:00 AEST / 19:00 AEDT.

---

## Task 1: Add the second schedule and branch the two affected steps

**Files:**
- Modify: `.github/workflows/nightly-update.yml`
- Test (throwaway, local only — not committed): `/tmp/validate_workflow.py`

This is a single logical change committed as one unit, so the workflow is never pushed in a half-branched state (e.g. second cron present but commit step not yet guarded — which would let an 18:00 run publish).

- [ ] **Step 1: Write the failing validation script**

Create `/tmp/validate_workflow.py` with the exact desired end-state assertions. It installs `pyyaml` into the repo `.venv` if missing (no system/global install, nothing committed):

```python
import subprocess
import sys

try:
    import yaml
except ImportError:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "pyyaml"], check=True
    )
    import yaml

PATH = ".github/workflows/nightly-update.yml"
text = open(PATH).read()
doc = yaml.safe_load(text)

# YAML 1.1 parses the bare key `on` as boolean True (the "Norway problem"),
# so accept either spelling.
on = doc.get("on")
if on is None:
    on = doc.get(True)

crons = [c["cron"] for c in on["schedule"]]
assert "0 20 * * *" in crons, f"missing 20:00 publish cron, got {crons}"
assert "0 8 * * *" in crons, f"missing 08:00 collect-only cron, got {crons}"

steps = doc["jobs"]["collect"]["steps"]
by_name = {s.get("name"): s for s in steps}

commit = by_name["Commit updated data"]
guard = commit.get("env", {}).get("IS_COLLECT_ONLY", "")
assert "github.event.schedule == '0 8 * * *'" in guard, (
    f"commit step missing IS_COLLECT_ONLY guard, got {guard!r}"
)
assert "[skip ci]" in commit["run"], "commit step missing the [skip ci] branch"

deploy = by_name["Trigger Pages deploy"]
assert deploy.get("if") == "github.event.schedule != '0 8 * * *'", (
    f"deploy step not gated to publishing runs, got if={deploy.get('if')!r}"
)

print("OK: workflow matches twice-daily / once-publish spec")
```

- [ ] **Step 2: Run the script to verify it fails against the current file**

Run: `.venv/bin/python /tmp/validate_workflow.py`
Expected: `AssertionError: missing 08:00 collect-only cron, got ['0 20 * * *']` (the first assertion to trip on the unmodified file).

- [ ] **Step 3: Add the second cron to the `schedule:` block**

In `.github/workflows/nightly-update.yml`, replace the current schedule block (lines 4-6):

```yaml
  schedule:
    # 20:00 UTC = 06:00 AEST (currently) / 07:00 AEDT (Oct-Apr in NSW/VIC/ACT/TAS/SA)
    - cron: "0 20 * * *"
```

with:

```yaml
  schedule:
    # 20:00 UTC = 06:00 AEST / 07:00 AEDT — publishing run (refreshes the live site)
    - cron: "0 20 * * *"
    # 08:00 UTC = 18:00 AEST / 19:00 AEDT — collect-only run (commits data, no deploy)
    - cron: "0 8 * * *"
```

- [ ] **Step 4: Branch the commit step so the collect-only run uses `[skip ci]`**

Replace the entire `Commit updated data` step (lines 43-54):

```yaml
      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          if git diff --staged --quiet; then
            echo "No data changes to commit"
            exit 0
          fi
          git commit -m "data: nightly update $(date -u +%Y-%m-%d)"
          git pull --rebase origin main
          git push
```

with:

```yaml
      - name: Commit updated data
        env:
          # True only for the 18:00 AEST collect-only schedule. Empty (→ false)
          # for the 20:00 publish schedule and for manual workflow_dispatch.
          IS_COLLECT_ONLY: ${{ github.event.schedule == '0 8 * * *' }}
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          if git diff --staged --quiet; then
            echo "No data changes to commit"
            exit 0
          fi
          if [ "$IS_COLLECT_ONLY" = "true" ]; then
            # [skip ci] keeps this data commit from triggering deploy.yml's
            # push trigger, so the live site is not rebuilt by the midday run.
            git commit -m "data: midday collect $(date -u +%Y-%m-%d) [skip ci]"
          else
            git commit -m "data: nightly update $(date -u +%Y-%m-%d)"
          fi
          git pull --rebase origin main
          git push
```

- [ ] **Step 5: Gate the deploy-trigger step to publishing runs**

Replace the `Trigger Pages deploy` step (lines 56-59):

```yaml
      - name: Trigger Pages deploy
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: gh workflow run deploy.yml --ref main
```

with:

```yaml
      - name: Trigger Pages deploy
        # Skip on the 18:00 collect-only run; publish on the 20:00 run and on
        # manual dispatch (where github.event.schedule is empty).
        if: github.event.schedule != '0 8 * * *'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: gh workflow run deploy.yml --ref main
```

- [ ] **Step 6: Run the validation script to verify it now passes**

Run: `.venv/bin/python /tmp/validate_workflow.py`
Expected: `OK: workflow matches twice-daily / once-publish spec`

- [ ] **Step 7: Manually confirm the conditional truth table**

Read the edited file once and confirm against this table (no command — a human/agent sanity check that the branching is internally consistent):

| Trigger | `github.event.schedule` | Commit message | `IS_COLLECT_ONLY` | Deploy step runs? | Push triggers deploy? |
|---|---|---|---|---|---|
| 20:00 schedule | `0 20 * * *` | `data: nightly update …` | `false` | yes (`!=` true) | yes (no skip-ci) |
| 08:00 schedule | `0 8 * * *` | `data: midday collect … [skip ci]` | `true` | **no** (`!=` false) | **no** (skip-ci) |
| `workflow_dispatch` | empty | `data: nightly update …` | `false` | yes (`!=` true) | yes (no skip-ci) |

Confirm: the only row where the site does **not** refresh is the 08:00 collect-only run. ✅

- [ ] **Step 8: Commit and push**

Per project convention, this repo pushes directly to `main`.

```bash
git add .github/workflows/nightly-update.yml
git commit -m "$(cat <<'EOF'
feat(workflow): add midday collect-only run, keep once-daily publish

Second cron at 08:00 UTC (18:00 AEST) collects and commits data with
[skip ci] so it lands on main without rebuilding the live site; the
20:00 UTC (06:00 AEST) run and manual dispatch publish as before.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
git pull --rebase origin main
git push
```

---

## Task 2: Live verification on GitHub Actions

The only authoritative end-to-end test of a scheduled workflow is observing real runs, because the collect-only path fires only on the `0 8 * * *` schedule (a `workflow_dispatch` run deliberately takes the publish path). Do this after the next 08:00 UTC and 20:00 UTC runs have occurred. **No code changes in this task** — it is a verification gate.

- [ ] **Step 1: Confirm both schedules are registered**

Run: `gh workflow view "Nightly Data Update" --ref main`
Expected: the workflow is listed as active. (GitHub does not enumerate cron entries here, but a parse error in the YAML would surface this workflow as having an error — its absence/error state is the signal to fix.)

- [ ] **Step 2: After the next 08:00 UTC run, confirm it did NOT deploy**

Run:
```bash
gh run list --workflow="Nightly Data Update" --limit 5
```
Identify the run whose start time is ~08:00 UTC. Then:
```bash
gh run view <run-id>
```
Expected: the `Trigger Pages deploy` step shows as **skipped**. Then confirm no deploy was triggered by the data push:
```bash
git log origin/main --oneline -5
gh run list --workflow="Deploy to GitHub Pages" --limit 5
```
Expected: the latest data commit message is `data: midday collect <date> [skip ci]`, and **no** "Deploy to GitHub Pages" run started at ~08:00 UTC.

- [ ] **Step 3: After the next 20:00 UTC run, confirm it DID deploy**

Run:
```bash
gh run list --workflow="Nightly Data Update" --limit 5
gh run view <20:00-run-id>
gh run list --workflow="Deploy to GitHub Pages" --limit 5
```
Expected: the 20:00 run's `Trigger Pages deploy` step shows as **success** (or skipped only if there were no data changes), the data commit is `data: nightly update <date>` (no `[skip ci]`), and a "Deploy to GitHub Pages" run started shortly after.

- [ ] **Step 4: Confirm the site refreshed once, in the morning**

Expected outcome over a full day: exactly one "Deploy to GitHub Pages" run per day (following the 20:00 UTC / 06:00 AEST collection), and the live dashboard's data reflects observations accumulated across **both** the prior 18:00 and the 06:00 collection windows (e.g. arrivals/probable-arrivals first seen in the evening window appear). The live "today" en-route figure is the 06:00 reading; historical daily entries settle to the 18:00 reading per the spec.

---

## Self-review notes

- **Spec coverage:** schedule (Task 1 Step 3), collect-only `[skip ci]` commit (Step 4), deploy gating (Step 5), `workflow_dispatch`→publish (Steps 4-5 conditions + truth table Step 7), no-double-counting (background; unchanged code), accepted daily last-write-wins behaviour (Task 2 Step 4) — all covered.
- **No placeholders:** every code/YAML/command block is complete and copy-pasteable.
- **Consistency:** the env var `IS_COLLECT_ONLY` and the cron strings `0 8 * * *` / `0 20 * * *` are used identically in the workflow edits, the validation script, and the truth table.
