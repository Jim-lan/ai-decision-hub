# Gemini Developer API qualification record

**Record date:** 2026-11-13
**Task/baseline:** C-007 · `g1-design-v2.0`
**Release status:** Disabled; not qualified for live dispatch

This record separates implementation conformance from owner/account permission. The
official adapter exists and is deterministically tested, but the repository contains
no credential and no evidence that a particular owner project currently has an
eligible model, paid data terms, quota, or a bounded approved spend. The registry
therefore remains `disabled`, with privacy `blocked` and pricing `unknown`.

## Required account evidence

| Field | Verified value | Disposition |
|---|---|---|
| Google project ID | Not provided | Blocks activation |
| Billing/usage tier | Not verified | Blocks activation; unpaid service is not accepted for owner data |
| Account/available region | Not verified | Blocks activation |
| Exact requested and returned model IDs | Not selected or live-verified | Blocks activation |
| Model input/output ceilings | Not account-verified | Blocks activation |
| Project RPM/TPM/RPD quotas | Not account-verified | Blocks activation |
| Input/output tariff and effective date | No model selected | Blocks activation |
| Owner run/day/month ceiling | Default zero | Blocks activation |
| Terms/data profile | Paid-service terms required | Blocks activation until account evidence confirms applicability |
| Non-sensitive live fixture | Not authorized or run | Required before claiming an operational provider at G4 |

## Official facts checked

- The official Python integration is `google-genai`; the adapter pins version
  `2.33.0`, uses the stable `v1` endpoint, one candidate, a bounded output, a request
  timeout, and SDK retries set to one total attempt. It forces the Gemini Developer
  API backend and official host, ignores environment proxy/backend selection, and
  does not follow redirects.
- SDK continuation and automatic function-calling loops are disabled, so one durable
  C-010 dispatch claim can produce only one HTTP request. No tools are configured and
  server-side response storage is disabled.
- The API response exposes `model_version` and usage metadata. The adapter rejects a
  known unexpected model version, preserves a missing version as unknown provenance,
  and maps prompt plus candidate/thinking output counts. Incomplete measured output
  usage remains unknown rather than being understated.
- Gemini rate limits are project- and model-specific, can change with account tier,
  and must be read from AI Studio. Daily quotas reset at midnight Pacific time.
- Under the terms effective 2026-03-23, unpaid-service prompts and responses may be
  used to improve Google products and may be reviewed; sensitive, confidential, or
  personal information must not be submitted. Paid-service prompts and responses
  are not used to improve products, but limited safety logging and processing terms
  still apply. This P0 adapter therefore requires paid-service evidence before
  activation.
- Prices and model availability vary by model and tier. A dated exact model tariff,
  quota, and hard local ceiling must be installed through the C-010 policy records;
  a generic pricing-page observation does not qualify the account.

Official sources checked on 2026-11-13:

- https://github.com/googleapis/python-genai
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/billing
- https://ai.google.dev/gemini-api/terms
- https://ai.google.dev/gemini-api/docs/zdr

## Activation gate

Activation requires an explicit owner-approved profile containing every field above,
an unexpired verification timestamp, an allowlisted paid-data profile, a nonzero but
bounded local budget, and a separate non-sensitive live smoke. If any model, tariff,
quota, terms, region, or returned identity changes, disable first and requalify. Never
store the API key in Git, this record, logs, prompts, exceptions, or exports.
