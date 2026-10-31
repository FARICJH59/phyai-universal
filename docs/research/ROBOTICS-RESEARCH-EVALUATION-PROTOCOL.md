# HOARE-Governed Robotics Research Evaluation Protocol

**Document timestamp:** 2026-10-22 11:40 UTC (07:40 EDT)  
**Repository:** `FARICJH59/phyai-universal`  
**Status:** Proposed simulation research protocol; not a result, safety case, certification, or production integration.

## 1. Purpose: the 5 Ws and How

- **Who:** Robotics and Physical AI researchers, lab engineers, and developers evaluating model-to-action workflows.
- **What:** Evaluate whether a shared authorization and evidence boundary improves the handling and analysis of proposed robotic actions.
- **Where:** First in software-only simulation; any later SIL/HIL or physical trial requires a separately approved integration and safety plan.
- **When:** During policy/model evaluation, fault-injection testing, regression testing, and post-run investigation.
- **Why:** A model's prediction or action proposal is not permission to cause a side effect. Researchers need a way to test authorization failures and correlate decisions with outcomes.
- **How:** Compare a baseline workflow with a governed workflow under matched tasks and hardware, inject defined faults, and report outcomes with reproducible run metadata.

## 2. Research question and hypotheses

**Primary question:** Under a fixed simulated robotics workload, does a governance boundary reliably prevent defined invalid or unauthorized proposals from reaching the simulated actuation function, while producing enough evidence to reconstruct each decision?

Pre-register these hypotheses before collecting results:

- **H1 — Enforcement:** All tested denial, escalation, stale, replayed, expired, revoked, malformed, or incorrectly bound authorization cases produce zero simulated actuation attempts.
- **H2 — Integrity:** Mutation of the proposal or its nested parameters after admission is detected before evidence commitment or simulated actuation, as applicable to the exercised path.
- **H3 — Traceability:** Each test run can be correlated across proposal, authorization decision, attempt, simulated outcome, and evidence identifiers without recording secrets.
- **H4 — Overhead:** Governance introduces measurable latency compared with the baseline. Quantify the distribution; do not assume it is negligible.
- **H5 — Reproducibility:** Given the same versioned code, dependencies, inputs, and deterministic seed where applicable, repeated simulation runs reproduce the same expected decision class.

These are hypotheses to test, not established performance claims.

## 3. Experimental arms

1. **Baseline:** Same simulator and task logic, without the shared admission/evidence boundary. The baseline must remain simulation-only and must not be used to justify unsafe physical execution.
2. **Governed:** Same simulator, task inputs, machine, and workload, with the Phase 16–17 boundary and a clearly labeled test-only authorization transport.
3. **Fault-injection arm:** Governed workflow with one controlled fault per case, including deny/escalate, timeout/exception, stale proposal, duplicate attempt, mismatched tenant/project/target/action/command/attempt, expired or revoked grant, verifier failure, post-admission parameter mutation, and out-of-range target command.

Record any differences between arms other than the governance boundary. Do not compare results if the task, machine, simulator version, or workload materially differs without documenting the difference.

## 4. Metrics and definitions

| Metric | Definition |
|---|---|
| Simulated task success | Completed simulated tasks / attempted simulated tasks, with task success criteria fixed in advance |
| Invalid-action escape count | Fault cases that reach the simulated actuation function despite the expected rejection |
| False rejection count | Valid test cases rejected contrary to the predeclared expected result |
| Decision correctness | Expected decisions matched / evaluated decision cases |
| Admission latency | Time spent in the admission/authorization segment, measured separately where instrumentation permits |
| End-to-end harness latency | Time from test invocation to terminal simulated result |
| Latency distribution | Sample count plus median, p95, and p99; include units and measurement method |
| Evidence completeness | Runs containing all required correlation fields / total runs |
| Reproducibility | Repeated cases with the same expected and observed decision/result under the declared environment |
| Resource overhead | CPU, memory, and energy only when measured with a documented tool and protocol |

Never present a local elapsed-time sample as a real-time guarantee, control-loop bound, p95/p99 result without sufficient samples, or production benchmark. Report failed runs and excluded data with reasons.

## 5. Minimum test procedure

1. Record UTC timestamp, commit SHA, branch, Python/runtime version, dependency state, operating system, machine class, command line, and simulator/test version.
2. Run the targeted unit tests, then the complete repository test suite. Preserve exact command output and exit codes.
3. Execute each valid and fault-injection scenario at least once as a correctness gate. For performance claims, determine and disclose a sample size before measuring; do not choose it after inspecting results.
4. Use the same task inputs and machine for baseline/governed comparisons. Randomize run order where practical and record seeds.
5. Capture proposal ID, attempt ID, target, expected and observed decision, rejection reason/category, simulated actuation count, outcome, and evidence references. Do not store tokens, private keys, credentials, or unnecessary personal data.
6. Repeat a subset of cases to test replay handling and reproducibility. Preserve the minimal failing input and seed for each failure.
7. Independently review any unexpected actuation attempt, missing evidence, or inconsistent result. Stop the evaluation if the harness itself violates the declared simulation-only boundary.
8. Publish raw aggregate counts, denominators, latency sample counts/distributions, exclusions, known limitations, and the exact commit/environment. Do not publish secrets or proprietary HOARE-CORE/AEGIS implementation details.

## 6. Acceptance gates

- **Correctness gate:** All predeclared test expectations pass; no invalid-action escape is observed in the tested cases.
- **Evidence gate:** Required identifiers and outcomes correlate for every included run, and evidence completeness is reported with a denominator.
- **Reproducibility gate:** Commands, versions, inputs, and results are sufficient for another researcher to repeat the simulation.
- **Performance gate:** Latency/resource results include a documented measurement method, sample count, distributions, and baseline comparison.
- **Integration gate:** Any real HOARE/AEGIS transport must use an approved, versioned contract and real authorization verification; test doubles must be unmistakably labeled.
- **Safety gate:** No transition to HIL or physical actuation until a separately reviewed hazard analysis, independent target safety controls, emergency-stop behavior, authority/revocation semantics, and an approved test plan exist.

Passing software tests is evidence only for the tested software paths and assumptions. It does not establish physical safety, functional-safety certification, production key management, a live HOARE endpoint, or safe behavior outside the test envelope.

## 7. Current scope and limitations

The associated governed-gripper demo is an in-memory simulation using injected mock admission/verifier components. It does not connect to a robot driver, ROS/DDS, physical I/O, or a production HOARE/AEGIS endpoint. The mock verifier does not prove cryptographic authorization. The Phase 16–17 integrity tests exercise software boundary behavior; they do not establish deployment-level revocation or lease/fencing integration.

This protocol defines a way to evaluate the research proposition; it contains no new experimental measurements or performance results.

## 8. Suggested results table

Fill this table only with measured results. Use `N/A` with a reason when a metric was not measured.

| Field | Baseline | Governed | Fault injection |
|---|---:|---:|---:|
| Commit SHA / environment | | | |
| Number of runs / cases | | | |
| Task successes / attempts | | | |
| Invalid-action escapes | | | |
| False rejections | | | |
| Evidence completeness (%) | | | |
| Admission latency median / p95 / p99 | N/A or measured | | |
| End-to-end latency median / p95 / p99 | | | |
| CPU / memory / energy measurement | | | |
| Failures and exclusions | | | |

## 9. Provenance

Created on 2026-10-22 at 11:40 UTC (07:40 EDT) for the public PHyAI-Universal research integration. Update this record additively when the protocol changes; preserve prior measurements and identify the commit/environment associated with every result.
