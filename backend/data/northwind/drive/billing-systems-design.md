# Billing Systems Design

> **Author:** Engineering — Billing Pod
> **Status:** Current

## Systems of record

- **Stripe** — payment processing and refunds. The source of truth for money movement.
- **Zendesk** — support tickets and the refund audit trail. Every refund is logged here with a reason code.
- **Salesforce** — pricing, discounts, credits. The source of truth for commercial terms.
- **Jira** — incident tickets and Deal Desk requests.

## Refund flow (system view)

1. Support Agent verifies the original charge in **Stripe**.
2. For amounts >= $500, the Billing Lead approves (Slack escalation).
3. Agent issues the refund in **Stripe** (original payment method only).
4. Agent logs the refund in the **Zendesk** ticket with the reason code.

## Integrations

- Stripe webhooks update the Billing dashboard in near-real-time.
- Zendesk tickets sync reason codes to a weekly fraud-review report.
- Refunds over the 2x hard limit are blocked at the Stripe config level and must be overridden by Finance.

## Roles

- **Support Agent** — issues standard refunds, escalates large ones.
- **Billing Lead** (Maya Chen) — approves refunds >= $500, handles fraud flags.
- **Head of Finance** — approves refunds beyond the 2x limit.
