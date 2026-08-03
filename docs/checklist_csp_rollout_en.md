---
title: "CSP Rollout Checklist"
project: "BookOasis"
category: "checklist"
date: 2026-08-03
tags: [security, csp, rollout, checklist]
---

# CSP Rollout Checklist (Report-Only -> Enforce)

This document is an operational checklist for moving BookOasis CSP safely from observation mode to blocking mode.

---

## 1. Prerequisites

1. The server must return `Content-Security-Policy-Report-Only` headers.
2. The CSP report intake endpoint must be enabled. (`POST /api/security/csp-report`)
3. The report file path must be valid. (default: `logs/csp_reports.jsonl`)
4. Collect reports under real traffic for at least 3 days.

---

## 2. Recommended Environment Baseline

```env
SECURITY_CSP_ENABLED=true
SECURITY_CSP_REPORT_ONLY=true
SECURITY_CSP_ENFORCE=false
SECURITY_CSP_LOG_REPORTS=true
SECURITY_CSP_REPORT_FILE=./logs/csp_reports.jsonl
SECURITY_CSP_REPORT_RATE_LIMIT_PER_MIN=120
SECURITY_CSP_REPORT_DEDUP_WINDOW_SEC=30
```

For high-traffic environments:
1. Lower `SECURITY_CSP_REPORT_RATE_LIMIT_PER_MIN` (for example: 60)
2. Increase `SECURITY_CSP_REPORT_DEDUP_WINDOW_SEC` (for example: 60)

---

## 3. Report-Only Observation Checks

1. Verify `Content-Security-Policy-Report-Only` exists on key routes including `/` and `/login`.
2. Verify `[CSP-REPORT]` logs or JSONL records are being written into `logs/csp_reports.jsonl`.
3. Over at least 24 hours, aggregate top fields:
   - `effective_directive`
   - `blocked_uri`
   - `source_file`
4. Confirm duplicate storms are controlled.

Pass criteria:
1. Per-minute suppression summaries are not persistently excessive.
2. Real functional violations are distinguishable from browser/platform noise.

---

## 4. Policy Refinement Order

1. Split top `blocked_uri` violations into internal static assets vs external assets.
2. Fix internal path/loading bugs first.
3. For external assets, allow only what is truly required (least privilege).
4. Do not remove broad exceptions (`unsafe-eval`, broad https allowances) all at once; reduce in stages.

---

## 5. Enforce Transition Gate

Switch only when all are true:

1. No critical functional blocking violations in the last 48 hours
2. Manual checks complete on login, library, viewer, settings, and plugin UI core flows
3. Operator rollback procedure is documented

Switch values:

```env
SECURITY_CSP_REPORT_ONLY=false
SECURITY_CSP_ENFORCE=true
```

---

## 6. Rollback Procedure

If issues appear, immediately set:

```env
SECURITY_CSP_ENFORCE=false
SECURITY_CSP_REPORT_ONLY=true
```

Then:
1. Restart server
2. Reproduce failing request
3. Inspect fresh violations and refine policy

---

## 7. Operational Recommendations

1. After frontend resource-structure releases, run 24h Report-Only observation
2. Validate plugin UI and external script path changes before rollout
3. Review top violations in `csp_reports.jsonl` at least monthly
