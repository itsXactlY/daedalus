# Legal / Policy / Operational Document Patterns

When producing long-form deliverables that are legal documents (bylaws, policies, terms), operational templates (quarterly reports, runbooks), or press/comms artifacts (press kit, branding guide) — apply these patterns in addition to the core `long-form-deliverable-production` skill.

## Universal frontmatter

Every legal/policy/operational document in a coordinated set opens with the same YAML-style header so the reader knows status at a glance:

```
**Document version:** v0.1
**Date:** 2026-MM-DD
**Status:** Draft (ready for review) | Pre-outreach; not yet sent | Design (pre-implementation)
**Companion to:** `docs/<category>/<related>.md`
```

The "Companion to" line is load-bearing: it anchors the document in the shared artifact set and prevents the reader from interpreting each policy in isolation. Use absolute path under the project's `docs/` tree.

## Universal footer

Every legal/policy document closes with a dated signature line that names the responsible role (never a person until incorporation is real):

```
**Signature**

_<Role> – <Project> Foundation_

Date: 2026-MM-DD
```

Roles used across the Stem Foundation set:
- Chief Legal Officer
- Chief Privacy Officer (or Data Protection Officer)
- Chief Security Officer
- Chief Brand Officer
- Director
- Communications Lead

## Section structure for policies

Legal/policy documents in this class follow a consistent section pattern. Adapt the count, but keep the rhythm:

1. **Overview** — 1-2 paragraphs stating purpose, scope, and audience. Name the project and the document's role in the broader set.
2. **Scope** — what is in, what is out. Be explicit about exclusions; the reader is a counterparty.
3. **Definitions** — controlled vocabulary, often as a table. For GDPR-aligned documents, define Personal Data, Processing, Data Subject, Sub-Processor.
4. **Substantive sections** — the body. Use numbered sections (1, 2, 3...) for legal documents; use named sections for ops/comms.
5. **Operational sections** — modifications, termination, governing law, contact.
6. **Signature** — the standard footer.

## Section structure for operational templates

Templates (annual report, quarterly report) follow a slightly different rhythm because the consumer is internal staff, not a counterparty:

1. **Header** — title, reporting period, publication date.
2. **Executive summary** — 2-3 paragraphs. Lead with the most important number.
3. **Metrics table** — early in the document, before narrative. The reader wants the numbers first.
4. **Body sections** — narrative with sub-headers per topic (operational, financial, security, etc.).
5. **Looking ahead / Upcoming activities** — never omit. The reader is planning.
6. **Contact** — multiple channels with response-time expectations.
7. **Signature** — the standard footer.

## Section structure for press / branding artifacts

Press kit and branding guide open differently — they are designed for scanning, not deep reading:

1. **Quick facts** — bullets or a 5x2 table. The journalist wants this in 30 seconds.
2. **Boilerplate** — three lengths (50/100/250 words). Always. The journalist will pick one.
3. **Visual identity** — links to assets, not embedded images. Keep the document text-searchable.
4. **FAQ** — exactly the questions a hostile or skeptical journalist will ask. Answer them straight, with the refusal clauses if relevant.
5. **Contact** — multiple channels with business hours.
6. **Signature** — the standard footer.

## Tiered production pattern

When the operator signals sustained execution ("weiter", "continue", "Tier-2 jetzt: 8 mehr deliverables"), produce in **labeled tiers** with explicit count:

- **Tier-1** — foundational deliverables (RFCs, charters, core code)
- **Tier-2** — policy/legal artifacts that operationalize Tier-1 (privacy, ToS, security, CLA)
- **Tier-3** — operational templates and comms artifacts (reports, branding, press kit)
- **Tier-4** — polish (video scripts, conference talk abstracts, peer-review drafts)

State the tier in chat before producing. After each tier, report verified byte/word counts in plain text (no markdown tables in chat). Tier progression is the operator's mental model — match it.

## Cross-document consistency

For a coordinated set (e.g., a foundation's full legal stack), enforce these consistencies:

- **Article numbers** — when bylaws cite refusal clauses as "Article 19", every other document that references them must say "Article 19" too. Search and verify.
- **Decision classes / role names** — if the RFC defines `decision_class: career | relationship | medical | financial | relocation`, the privacy policy's data categories must use the same vocabulary, not "decision types" or "categories of choice".
- **Worked example character** — if the RFC and pitch deck use M (28, NYC, startup vs large co) as the worked example, the press kit boilerplate and the simulation engine's marketing demo must use M. The character is the trust anchor.
- **Date convention** — ISO 8601 throughout (`2026-06-18`), never "June 18, 2026" or "18/06/2026".
- **Versioning** — every document carries `**Document version:** vX.Y` in the frontmatter. Bump consistently across the set when one doc changes.

## Pitfalls specific to legal/policy work

- **Confident numbers on legal risk.** Use ranges, not point estimates. "60/40 estimate" is honest; "we will face no legal challenges" is fabricated.
- **Promising compliance you cannot guarantee.** GDPR, FADP, SOC 2 are aspirational targets until the audit completes. Phrase policies as targets the Foundation works toward, not as facts.
- **Inconsistent date formats.** Mixing ISO and "Month DD, YYYY" looks unprofessional and breaks search. Lock the format.
- **Inconsistent signature role naming.** "Chief Legal Officer" in one doc, "Legal Lead" in another. Pick the role names once, use them everywhere.
- **Missing "Companion to" line.** Without it, a reader cannot navigate the set. Always include.
- **Omitting the governing-law clause.** Swiss foundation law (or Delaware, or whatever applies) must appear in every legal document that creates obligations. Never leave this implicit.
- **Failing to name the legal form.** A foundation, an LLC, and a coop have different default rules. State the form in the Scope section of every legal document.
- **Publishing a policy that contradicts a higher-tier document.** A privacy policy that contradicts the bylaws is a bug. Treat the bylaws/charter as the root and reconcile downward.
- **Confusing "MAY" (RFC 2119) with "may" (English).** In technical specs the case matters. In legal/policy documents, "may" is just English; reserve RFC 2119 for RFC documents.
