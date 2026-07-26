# Incident Response Runbook

> **Owner:** Engineering On-Call
> **Severity levels:** SEV1 (outage), SEV2 (degraded), SEV3 (minor)

## On-call rotation

The on-call engineer is paged via PagerDuty. The current rotation schedule lives
in the `#eng-oncall` channel topic.

## Triage (first 15 minutes)

1. Acknowledge the page in PagerDuty.
2. Post in `#eng-incidents` with a short initial summary ("investigating SEV2
   checkout errors").
3. Create a Jira incident ticket linked from the PagerDuty alert.

## Mitigation > root cause

Prioritise restoring service over understanding why. Roll back the most recent
deploy if it's a likely cause. Communicate status to `#status` every 30 minutes
for SEV1, hourly for SEV2.

## Post-incident

Within 2 business days, the incident lead writes a blameless postmortem in the
`incidents/` Drive folder. Action items become Jira tickets assigned with owners
and due dates.

## Related policies

- Deploy windows: no production deploys after 3pm Friday without a Director's
  sign-off (see `deploy-policy.md`).
