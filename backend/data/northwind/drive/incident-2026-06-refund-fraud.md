# Postmortem: Refund Fraud Spike (2026-06-10)

> **Severity:** SEV2
> **Lead:** oncall-eng
> **Status:** Resolved

## Summary

A coordinated group of ~40 newly-created accounts submitted refund requests
within a 2-hour window, attempting to abuse the refund flow. Caught by a Support
Agent (leo.m) who noticed the pattern in `#support`.

## Timeline

- 14:02 — leo.m flagged the spike in `#support` and held the refunds.
- 14:05 — Billing Lead (maya.c) paged eng-oncall.
- 14:08 — On-call rolled back a recent signup-flow deploy as a precaution.
- 14:20 — Confirmed the accounts shared payment fingerprints; refunds denied.
- 15:00 — Deployed a rate-limit on refund requests per account per day.

## What went well

- Frontline agent caught the pattern fast.
- Hold-then-escalate reflex prevented any fraudulent payouts.

## Action items

1. Add automated anomaly detection on refund volume (Jira BILL-412, owner: eng).
2. Document the fraud-hold process in the refund runbook (done).
3. Quarterly review of repeat-refund accounts (owner: Billing Lead).

## Lesson

The "hold and escalate" behavior that prevented loss here is exactly the
behavior codified in the refund policy: amounts over $500 escalate, and anything
suspicious gets held for the Billing Lead.
