# RFC Section Structure — Concrete Template

This is the section structure used for technical specifications (RFCs, protocol specs, design docs with conformance requirements). Use this template for each section of the foundational deliverable.

## Section anatomy

Each section has the following parts, in order:

### 1. Section header

```markdown
# <Project Name> Protocol — RFC v<MAJOR>.<MINOR>, Section <N>

## Section <N> — <Title>
```

The title should be a noun phrase, not a verb phrase. "Data Model" not "Specifying the Data Model". "Cryptographic Primitives" not "How Cryptography Works".

### 2. Section opener (one paragraph)

Open with one paragraph that explains what the section covers and why it exists. Example:

> This section specifies the canonical structure of all Branches and related objects. Implementations MAY use internal representations that differ from the canonical form, but the Conformance Suite requires that any Branch transmitted between implementations or to the Federation Sync service serialize to the canonical form defined here.

This paragraph is mandatory. It does three things:
- States the section's scope
- States what is normative (MUST / MAY) vs descriptive
- Connects to the rest of the protocol via cross-reference

### 3. Body content

Write at ~350 words/page density. Use:

- **Subsections (3.x)** for major content blocks
- **Code blocks** for schemas, examples, primitives
- **Tables** for option matrices
- **Bullet lists** for enumerations, not for prose

Every MUST corresponds to a Conformance Suite test. Every SHOULD corresponds to a recommended test. State these explicitly.

### 4. Worked example

Where appropriate, include a worked example that illustrates the section's concepts. The worked example uses the shared character set (e.g., "M, 28, NYC, software engineer") so it recurs across sections and across deliverables.

Worked example pattern:

```markdown
### <N.M> Worked example

Extending the Branch from Section <X>, <character reference> would have proceeded as follows.

**Step 1 — <Action>.** <Character> <did what>.

**Step 2 — <Action>.** ...

After <N> steps, <outcome>.

The Branch is encrypted under <character>'s Branch Key before persistence.
```

### 5. Conformance notes (mandatory closer)

End every section with a "Conformance notes" subsection:

```markdown
### <N.M> Conformance notes for this section

Implementations claiming conformance to v<MAJOR>.<MINOR> MUST:

- <Requirement 1>
- <Requirement 2>

Implementations SHOULD:

- <Recommendation 1>

The Conformance Suite verifies all MUSTs.
```

This subsection is the testable contract for the section. It maps directly to Conformance Suite test cases.

### 6. Bridge to next section

End the section with one sentence that points to the next section:

```markdown
This concludes Section <N>. Section <N+1> specifies <next section's scope>.
```

This bridges sections and signals the document's flow.

## Conformance language reference (RFC2119)

| Term | Meaning |
|---|---|
| MUST / REQUIRED / SHALL | Absolute requirement. Implementations that fail this are non-conformant. |
| MUST NOT / SHALL NOT | Absolute prohibition. |
| SHOULD / RECOMMENDED | Strong recommendation. May have valid reasons to ignore, but the implications must be understood. |
| SHOULD NOT / NOT RECOMMENDED | Strong discouragement. |
| MAY / OPTIONAL | Truly optional. |

When you write "MUST", also write the corresponding Conformance Suite test. The Suite is the operational definition of conformance.

## Worked-example character template

Pick a worked-example character early. The character should be:

- Specific enough to feel real (name, age, occupation, location)
- Generic enough to recur across deliverables (a 28-year-old software engineer is more reusable than a 47-year-old doctor)
- Representative of the project's target audience

Template:

```
Name: <NAME>
Age: <AGE>
Location: <CITY>
Occupation: <OCCUPATION>
Decision context: <DECISION CLASS>, e.g. "stay at startup vs. take large-co role"
Quantitative context: <NUMBERS>, e.g. "$80k student debt, $95k income, partner earning $60k"
```

The character recurs in:
- RFC worked examples (Section 3 schema, Section 5 capture flow, Section 6 simulation, Section 8 heir transfer)
- Pitch deck killer demo (slide 2)
- Foundation case studies
- Marketing copy

Recurrence is what makes a multi-file deliverable set feel coordinated.

## Honest-unknowns enumeration

Every foundational deliverable should include a "What I still don't know" subsection or appendix. Format:

```markdown
### What I still don't know

Honest gap list. Each of these is a real unknown.

- **<Unknown 1: specific question>.** <Why it's uncertain>. <Best estimate with confidence>.
- **<Unknown 2>.** <Why>. <Estimate>.
- **<Unknown 3>.** <Why>. <Estimate>.

The unknowns are load-bearing for the deliverable's credibility. Hiding them
undermines the work.
```

The unknowns should be specific ("whether the simulation engine's calibration trajectory reaches honestly-useful within 5 years") not generic ("we may face challenges").

## Section length targets

For a 150-200 page RFC, section length targets:

| Section | Pages | Rationale |
|---|---|---|
| 1 — Abstract + Motivation | 5 | Sets the stage; not too dense |
| 2 — Terminology | 10 | Glossary density |
| 3 — Data Model | 25 | Schema + worked example; the load-bearing section |
| 4 — Cryptographic Primitives | 15 | Dense; references external standards |
| 5 — Capture Protocol | 15 | Multi-role, multi-state |
| 6 — Simulation Interface | 20 | Constraint layer + LLM integration |
| 7 — Storage & Sync | 10 | Operational spec |
| 8 — Heir Transfer | 15 | State machine + UX |
| 9 — Conformance Requirements | 15 | Suite structure + cert process |
| 10 — Security Considerations | 15 | Threat model + crypto agility + incident response |

If a section is significantly under target, expand with worked examples. If significantly over, split.

## Cross-file consistency checklist

After producing all sections, verify:

- [ ] The worked-example character appears in at least 3 sections
- [ ] The controlled vocabulary is defined in Section 2 and used consistently
- [ ] All MUSTs have corresponding Conformance Suite tests referenced
- [ ] The honest-unknowns list appears in Section 1 (motivation) and is expanded in a dedicated section or appendix
- [ ] Cross-references between sections use the form "Section X.Y" not "see above" or "see below"
- [ ] The closing reflection of Section 10 explicitly addresses the load-bearing honest unknown

If any check fails, fix before declaring the deliverable complete.
