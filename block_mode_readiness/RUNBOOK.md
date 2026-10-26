# Block Mode Readiness — Runbook

This runbook walks you through measuring whether your Endor Labs PR action policies are ready to move from **warn** to **block**: how to run the report, how to read it, how to keep the data history across your rollout, and how to complete the false-positive review. For full flag and file reference, see [README.md](README.md).

The examples use a fictional tenant: namespace `example-corp`, display name `Example Corp`, and rollout project tags `payments-api`, `mobile-banking`, `core-ledger`, `loan-servicing`, `loan-servicing-apps`. Substitute your own values.

## What the report answers

While policies are in warn mode, nothing stops a merge. Before you switch to block, the report gives you evidence from the actual PR checks on the repositories in your rollout:

| Question | Where to find it |
|---|---|
| What percentage of PR checks would have failed in block mode? | **Section A.** Every PR check in your tagged scope is the denominator, including clean checks, so the impact is not overstated by looking only at scans that warned. |
| Is the expected friction widespread or concentrated in a few repos? | **Section B.** Repositories generating warnings, their individual rates, and how many tagged repositories had no warnings at all. |
| Which findings are true positives versus false positives? | **Section C** and `fp_worksheet.csv`, one row per warning finding with links to the PR, scan, and Endor finding. |
| Are developers responding to warnings? | **Section D.** Scans of the same PR are grouped to show whether warning counts decreased, cleared, remained open, or had only one scan. |

Section D measures **subsequent Endor PR scans only**. It does not query GitHub and makes no claim about whether a PR was merged.

The tool is tenant-agnostic: your namespace, project tags, dates, and display name are passed as command-line arguments, so you can run, extend, and adapt it yourself.

## 1. Set up

```bash
git clone https://github.com/Endor-Solutions-Architecture/scripts.git
cd scripts/block_mode_readiness
python -m pip install -r requirements.txt
endorctl auth login
```

If you already have the repository cloned, pull the latest `main` instead.

You need Python 3.8+ and `endorctl` on your `PATH`, authenticated against your tenant.

## 2. Confirm your rollout project tags

The report is scoped by **project tags** — the same tags you use to enable repositories and bind your action policies. It never falls back to the whole tenant.

```bash
python list_project_tags.py -n example-corp
```

This prints every unique project tag in your namespace (including child namespaces). Pick the tags that define your rollout.

## 3. Run a collection and report

```bash
python main.py run \
  -n example-corp \
  --project-tags payments-api,mobile-banking,core-ledger,loan-servicing,loan-servicing-apps \
  --days 21 \
  --customer "Example Corp"
```

Optional flags:

- `--decision-date YYYY-MM-DD` — your target block-mode decision date, shown on the cover and in next steps.
- `--mark-date KEY=YYYY-MM-DD` (repeatable) — splits Section A before and after an event such as a policy being enabled, e.g. `--mark-date sast=2026-09-01`.

If the tags match zero projects, the run exits with an error — check the spelling against step 2.

Output is written to a new timestamped folder:

```text
generated_reports/block_mode_readiness/example-corp/<timestamp>/
```

## 4. Read the output

| File | What it is for |
|---|---|
| `readiness_report.pdf` | The decision document: Sections A–D, caveats, and next steps. |
| `readiness_dashboard.html` | Interactive version of the same data. Self-contained; opens offline in any browser. |
| `pr_checks.csv` | One row per PR check, **including clean checks** — the detail behind the would-have-blocked rate. |
| `fp_worksheet.csv` | One row per warning finding, for your security team to label (step 7). |
| `pr_trajectories.csv` | One row per PR that warned, with its warning-count sequence (e.g. `3→3→1→0`) and classification. |
| `summary.json` | Headline metrics for automation and week-over-week comparison. |
| `snapshot.json`, `meta.json` | The collected data and collection metadata. **Keep these** — they are needed to build a cumulative report beyond the API retention window. |

### Interpreting the results

Here is how a typical first report might read:

> 198 tagged projects · 841 PR checks · 36 warned · **4.3% would-have-blocked** · 0 blocked (expected in warn mode) · 185 of 198 projects with no warnings · top five repositories account for 77.8% of warned checks.

- **A low rate concentrated in a few repositories** usually means you can address those repositories directly rather than delay the whole rollout.
- **Blocking outcomes should be 0** while enforcement is in warn mode.
- **No SCA or secrets findings** means none of the collected PR checks produced a *new or changed* finding that matched those PR policies. It does **not** mean your repositories have no main-branch vulnerabilities or secrets.
- **History starts at your first collection.** PR checks older than the API retention window when you first ran the tool cannot be recovered, and the report states this.
- **Section D classifications:** `acted` means a later scan had fewer warnings than the first; `cleared` means it reached zero; `still_open` means later scans did not reduce the count; `single_scan` means there was only one scan — not that the warning was ignored at merge.
- **The false-positive rate stays blank** until your security team labels the worksheet (step 7).

## 5. Collect weekly

Endor retains PR scan results in the API for **21 days**. Setting `--days` above 21 cannot recover data that has already aged out.

- Run step 3 **at least weekly**, ideally from the first week of warn mode.
- Each run creates a new timestamped folder and never overwrites earlier ones. **Do not delete them** — together they are your rollout history.
- Weekly windows can overlap; scans are deduplicated by UUID when the cumulative report is built.
- `generated_reports/` is not committed to Git. Back up the snapshot folders to a secure shared location. If several people run collections, bring their timestamped folders together under the same `generated_reports/block_mode_readiness/<namespace>/` directory.

## 6. Build the cumulative report

When you are ready to review the full rollout period:

```bash
python main.py report \
  --snapshot-dir generated_reports/block_mode_readiness/example-corp
```

This creates a `union-<timestamp>/` folder with the cumulative PDF, dashboard, and CSVs. It does not modify your original snapshots and does not call the Endor API.

## 7. Complete the false-positive review

1. Build the cumulative report (step 6).
2. Open the resulting `fp_worksheet.csv`.
3. For each row, set:
   - `fp` = `yes` if it is a false positive, `no` if it is a true positive
   - `reason` = the rationale for your decision
4. Do **not** change the finding or scan UUID columns — they are used to match labels to findings.
5. Rerun the report with the completed worksheet:

```bash
python main.py report \
  --snapshot-dir generated_reports/block_mode_readiness/example-corp \
  --labels /path/to/completed_fp_worksheet.csv
```

The regenerated PDF and dashboard include the false-positive rate per finding and per PR, overall and by violation type. Any label rows that do not match a finding are listed in the report rather than silently dropped.

## 8. Make the decision

With the cumulative report and labeled worksheet you have the evidence for the warn-to-block decision:

- the would-have-blocked rate across the full rollout period (Section A);
- which repositories would carry the friction (Section B);
- the false-positive rate, overall and by violation type (Section C);
- whether developers are already acting on warnings (Section D).

Keep collecting weekly after the decision if you want to track the effect of block mode, or to roll the same process out to the next set of tagged projects.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `no projects matched project tags` | Tag names don't match. Re-run `list_project_tags.py` and copy them exactly. |
| `endorctl` errors | Not authenticated or wrong namespace. Run `endorctl auth login` and check `-n`. |
| `mixed namespaces` from `--snapshot-dir` | Snapshots from different namespaces are in the same folder. Keep one namespace per directory. |
| Fewer PR checks than expected | Only scans tagged with a PR count; other CI runs are excluded (counted in `meta.json` as `ci_runs_dropped_no_pr`). Also check the 21-day retention window. |

You are free to run, modify, and extend the script to fit your process.
