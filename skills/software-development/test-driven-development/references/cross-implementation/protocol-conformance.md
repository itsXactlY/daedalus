
# Protocol Conformance Test Suite

Build a conformance test suite that verifies implementations against a formal protocol specification. The suite is the operational definition of "passing" — implementations claim conformance by running it.

## When to use

- Implementing a protocol with formal MUST / MUST NOT / SHOULD requirements (RFC, W3C, IETF, working draft, internal company spec)
- The spec has controlled vocabularies, schemas, or normative language
- Need to verify third-party implementations against the spec
- Cryptographic, distributed systems, civilizational infrastructure, or any spec where ambiguity is dangerous
- The spec author wants to publish a testable normative definition, not just prose

Do NOT use for:

- Test-driven development of application code (use `test-driven-development` instead — different philosophy: spec is the source of truth, not the tests)
- Unit-testing internal implementation details of a single project
- Integration testing of a single implementation
- Throwaway exploratory work (use `spike`)

## Steps

### 1. Spec audit

Read the entire spec end-to-end. Build a numbered coverage map:

| Section | Requirement | Test ID | Test name |
|---------|-------------|---------|-----------|
| 3.4.1 | `branch_class` MUST be in vocabulary | schema-01 | branch_rejects_invalid_branch_class |
| 4.3 | Each encryption MUST use a unique nonce | crypto-12 | nonce_reuse_detected |
| ... | ... | ... | ... |

Every MUST must map to at least one test. MUST NOTs map to negative tests. SHOULD / MAY are advisory — note them but don't block on coverage.

If a MUST can't be tested (it's aspirational, or tests would be tautological), flag it for the spec author. A MUST that can't be tested is a documentation bug.

### 2. Choose language and structure

Match the reference implementation's language. For Rust, a separate crate (e.g., `protocol-conformance/`) or a `tests/` directory in the implementation crate. For Python, `pytest`. For Go, `_test.go` files.

The suite is a separate artifact from the implementation. The ideal structure:

- Implementations import or vendor the suite
- The suite does NOT import the implementation's internals (treat the implementation as a black box where possible)
- Shared fixtures (e.g., worked examples in JSON) live with the suite, not the implementation

This separation means the suite can verify multiple implementations against the same spec without modification.

### 3. Write the worked example first

Before any test logic, write a complete, valid example that exercises the full pipeline. This is your "smoke test" — it catches parsing issues, schema mismatches, and integration problems before you write 50 tests that all hit the same bug.

The worked example should:

- Use realistic data (not synthetic `{"a": 1, "b": "x"}`)
- Cover the most complex path through the protocol
- Be referenced from the spec itself, so spec readers see real data
- Be testable as a unit (`cargo run --example worked_example`)

### 4. Positive tests (per-MUST coverage)

For each MUST, write a positive test: valid input → passes. Tag the test with the spec section number either in the test name or in a comment:

```rust
#[test]
// RFC v0.1 §3.4.1 — decision_class controlled vocabulary
fn schema_decision_class_accepts_controlled_vocabulary() {
    for class in CONTROLLED_VOCABULARY {
        assert!(validate_decision_class(class).is_ok());
    }
}
```

The tag is for traceability — when the spec changes, you need to find the affected tests fast.

### 5. Negative tests (per-MUST-NOT coverage)

For each MUST NOT and each invariant, write a negative test: invalid input → rejected. Cover:

- Malformed syntax (invalid JSON, broken signatures)
- Wrong types (string where number expected)
- Missing required fields
- Out-of-range values (negative counts, scores outside [0, 1])
- Invalid enum values (case-sensitivity is a common gotcha — `"Personal"` is NOT `"personal"`)
- Hash chain breaks (modify one byte, expect rejection)
- Signature mismatches

### 6. Adversarial tests

Negative tests cover "invalid by mistake." Adversarial tests cover "invalid by attack" — the kinds of malformed inputs a malicious party would construct:

- **AAD-swap attacks.** Encrypt under one AAD, swap to another in the envelope, expect decryption failure.
- **Nonce reuse.** Verify the suite detects (or, per the spec, requires preventing) nonce reuse.
- **Hash substitution.** Replace one hash in a chain with another valid-looking hash, expect rejection.
- **Cross-implementation compatibility.** A Branch produced by implementation A must parse by implementation B.

These are not redundant with negative tests — they target the security boundary, not the validation boundary.

### 7. Run, fix, iterate

Run the suite. If it fails, fix the **implementation**, not the test (unless the test encodes the wrong requirement — verify against the spec).

A test that fails because the implementation is wrong is a feature, not a bug. That's the whole point.

Iterate until all tests pass. Each iteration tightens both the spec's normative definition and the implementation's correctness.

### 8. Publish the suite as a separate artifact

The suite is open source under the same license as the spec. Publish it in a separate repository (or as a subdirectory clearly delineated from the implementation) so third-party implementations can vendor it.

The suite's README should explain:

- How to run it
- The version of the spec it tests against
- How to interpret failures (which test failed, what section of the spec it maps to, what the expected vs actual behavior is)
- How to report false positives (where the test is wrong, not the implementation)

## Pitfalls

### JSON fixtures with placeholder hashes

When a worked example's JSON uses illustrative placeholder hashes (typical for spec examples that want to be readable but aren't real cryptographic outputs), hash-chain verification will reject them because it computes different real hashes.

Three options, in order of preference:

1. Compute the real hash and put it in the fixture.
2. Use structural-only verification (`verify_chain` checks predecessor links, not content) for the example only.
3. Add a comment in the spec and the fixture explaining that the hash is illustrative.

Do NOT hand-edit hashes to match — they'll get out of sync as soon as the fixture is regenerated.

### Doc-test pseudocode

Rust doc comments with pseudocode get parsed as Rust by `cargo test --doc`. If the pseudocode contains variables or operators that aren't valid Rust, the doctest fails.

Wrap pseudocode in a ```text fence (NOT ```rust):

```rust
/// Pseudocode (not Rust):
///
/// ```text
/// entry_content_hash = SHA-256(
///     predecessor || role || key || type || timestamp || ...
/// )
/// ```
```

### Enum errors with borrowed values

An `Error` enum with `Vec<&'static str>` plus a function taking `&[&str]` causes E0521 (borrowed data escapes outside the function). Use `Vec<String>` and convert at the call site:

```rust
#[derive(Error)]
pub enum Error {
    InvalidEnumValue {
        field: String,
        got: String,
        expected: Vec<String>,  // not Vec<&'static str>
    },
}

pub fn check_enum(field: &str, value: &str, allowed: &[&str]) -> Result<()> {
    // ...
    Err(Error::InvalidEnumValue {
        expected: allowed.iter().map(|s| s.to_string()).collect(),
    })
}
```

### Patches can break files in subtle ways

When patching a file — especially after partial edits — the patch tool can insert new content inside an existing function declaration (e.g., adding `pub fn check_enum(...)` body lines in the middle of an `pub fn check_enum<T>(...)` signature line, creating an unclosed delimiter). The file then fails to compile with cryptic errors.

Mitigation: re-read the file or run a syntax check after every multi-file patch batch. If the patch tool reports an error mentioning "unclosed delimiter" or "expected expression," look at the patched region — the new content is probably inside the wrong scope.

### Coverage map vs implementation drift

The spec changes. The implementation changes. The suite changes. Keep the coverage map (Step 1) in the suite's repository, not in a wiki or a doc. When the spec changes, update the map first, then update the tests, then update the implementation. If the map drifts, the suite's coverage silently erodes.

### Worked-example fixtures vs verifier

If the worked example's JSON fixture uses illustrative placeholder hashes (because the spec author wanted readability over cryptographic exactness), the verifier will reject them. See the first pitfall above.

## Verification

A conformance suite is done when:

- `cargo test` (or equivalent) reports all tests passing.
- Every MUST in the spec has at least one corresponding test, verified by walking the coverage map.
- Every MUST NOT has at least one negative test.
- Adversarial tests cover AAD swap, nonce reuse, hash substitution, and cross-implementation parse.
- The worked example runs end-to-end (`cargo run --example` or equivalent).
- The suite is published separately from the implementation, with a clear README explaining how to run and interpret it.
- The coverage map is in the suite's repository and up to date.

## What this skill is NOT

- Not RED-GREEN-REFACTOR for application code (use `test-driven-development`).
- Not internal unit testing (the suite tests the public surface, not implementation details).
- Not a single-implementation integration test (the suite is portable).
- Not a substitute for code review (use `requesting-code-review` for code quality).

## Related skills

- `test-driven-development` — for app code where tests come first and drive the design
- `systematic-debugging` — when the suite reveals a bug in the implementation
- `writing-plans` — for planning the implementation work that the suite will verify
- `subagent-driven-development` — for parallelizing the implementation across multiple agents

## Reference patterns

A reference implementation of this pattern: see `stem-conformance` Rust crate at `/home/alca/stem-conformance/` for the Stem Protocol v0.1 RFC suite — full worked example, 38 passing tests covering schema/crypto/provenance/layer-constraints/adversarial categories.
