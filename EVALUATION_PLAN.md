# ModBusX Evaluation Plan (DECIDE Framework)

This evaluation framework follows the **DECIDE** model (Preece, Rogers & Sharp, 2015) as applied to the ModBusX usability evaluation conducted during Sprints 7-8.

## 1. Determine the aims and goals

**What are the high-level objectives of the evaluation?**
To validate that ModBusX meets the minimum usability thresholds required for adoption by QA engineers and solar PV integration testers within GoodWe's IoT R&D department, as specified by NFR06 (intuitive interface), NFR07 (contextual help), and NFR08 (clear error messages).

**Who wants it and why?**
The industry supervisor and the department's QA lead need evidence that ModBusX can replace or supplement existing tools (Modbus Slave Simulator, ModScan32) without requiring extended training, and that the interface is sufficiently learnable for first-contact use.

**Goals:**
1. **Assess efficiency:** Verify that users can configure a multi-slave environment and begin simulation faster in ModBusX than in existing tools.
2. **Assess learnability:** Determine whether the tree-based device hierarchy reduces cognitive load compared to the multi-window interface used by competitors.
3. **Assess error rate:** Determine whether address entry errors are reduced by the AddressModeManager and associated UI affordances.
4. **Identify specific problems:** Pinpoint usability issues for iterative remediation.

## 2. Explore the questions

**Primary Questions:**
1. Can a user configure a multi-slave Modbus simulation environment and begin communication verification within acceptable time thresholds?
2. Does the tree-based connection/slave/register hierarchy reduce cognitive load compared to flat multi-window tools?
3. Are address entry errors reduced by the AddressModeManager toggle?

**Sub-questions:**
1. **Setup efficiency:** How long does it take to create a TCP connection, add a slave, and configure a register group from a cold start?
2. **Data entry clarity:** Can users switch between display formats (Unsigned, Signed, Hex, Binary) without confusion?
3. **Log discoverability:** Can users locate specific RX/TX traffic entries in the communication log?

## 3. Choose the evaluation approach/method

**Paradigm:** Formative usability evaluation (task-based lab study).
**Methods:**
- **Primary:** Controlled task-based study collecting quantitative performance metrics (task success rate, time on task, click count, errors).
- **Secondary:** System Usability Scale (SUS) — a validated 10-item post-task questionnaire yielding a composite usability score on a 0-100 scale (Brooke, 1996).
- **Qualitative:** Concurrent Think Aloud (CTA) protocol capturing observations during task execution, followed by a brief debrief interview.

**Design:** Single-tool formative study (not within-subjects comparison). Comparative timings against baseline tools (Modbus Slave Simulator, ModScan32) were performed by the evaluator separately for directional benchmarking.

## 4. Identify practical issues

- **Participants:** 3 participants from within the department — 2 QA engineers (P1, P2) and 1 firmware developer (P3). All familiar with Modbus protocol and at least one competing tool, but none had used ModBusX before. Sample size consistent with Nielsen's (1994) finding that 3-5 evaluators identify the majority of usability problems in formative evaluations.
- **Language:** Chinese UI was used (all participants are native Chinese speakers). SUS was administered in English.
- **Equipment:**
    - **Tool:** ModBusX (latest build, Chinese language pack active)
    - **Environment:** Windows desktop, standard department workstation
- **Target thresholds:** Agreed in advance with industry supervisor and QA lead, calibrated by task complexity:

| Task Category | Target Success Rate | Target Time | Rationale |
|---|---|---|---|
| Routine actions (e.g., TCP connection) | >=95% | <60s | Near-trivial for Modbus practitioners |
| Intermediate configuration (e.g., slave + register group) | >=85-90% | <90s | Requires tree navigation understanding |
| Data entry (decimal/hex) | >=90% | <10-15s | Inline editing with format switching |
| Secondary UI elements (e.g., log pane) | >=80% | <30s | Accounts for first-exposure learning |

- **Metrics collected per phase:**
    - Elapsed time (from intent to visible completion)
    - Number of mouse clicks
    - Errors and hesitation moments
    - Think-aloud observations

## 5. Decide how to deal with ethical issues

- **Informed Consent:** Participants were briefed on the study's purpose and agreed to observation and data collection.
- **Anonymity:** Participants are identified only as P1, P2, P3. No names appear in data or reports.
- **Right to withdraw:** Participants could stop at any time without consequence.
- **Minimal orientation:** One sentence of context provided ("This is a Modbus slave simulator. Please perform the tasks I describe, speaking your thoughts aloud as you work.") — no further instruction or demonstration, to measure first-contact learnability.

## 6. Evaluate, analyze, interpret and present data

### Task Design (4 Sequential Phases)

**Phase 1 — Setup and Connection:**
- Launch the application and start a Modbus TCP server listening on port 5020.
- Tests: discoverability of "Add Connection" action, clarity of server status feedback (red/green dot).
- Maps to: NFR06, Heuristic H1 (Visibility of System Status).

**Phase 2 — Memory Map Configuration:**
- Add a new slave with ID 2 to the existing connection; create a Holding Register group starting at address 40001 with 10 registers.
- Tests: tree hierarchy navigation, address mode comprehension.
- Maps to: NFR06, NFR07, NFR08, Heuristics H2 (Match System/Real World), H6 (Recognition vs Recall).

**Phase 3 — Data Entry:**
- Set Register 40001 to decimal value 250; set Register 40002 to hexadecimal value 0xFFFF.
- Tests: inline editing flow, display format switching via Type column.
- Maps to: NFR08, Heuristics H5 (Error Prevention), H8 (Aesthetic/Minimalist Design).

**Phase 4 — Traffic Monitoring:**
- Locate the most recent RX (receive) packet in the communication log.
- Tests: log pane discoverability and readability.
- Maps to: NFR07, Heuristics H1 (Visibility of System Status), H4 (Consistency/Standards).

### Quantitative Results Summary

**Task Success Rate (first attempt, no evaluator intervention):**

| Task | Target | Observed | Notes |
|---|---|---|---|
| Create TCP connection | >=95% | 100% (3/3) | All found toolbar icon independently |
| Add Slave ID | >=90% | 100% (3/3) | P1 tried right-click first, self-corrected |
| Create register group | >=85% | 67% (2/3) | P2 confused by PLC vs Protocol addressing |
| Modify register value | >=90% | 100% (3/3) | Type column dropdown located within 15s |
| Locate log entry | >=80% | 67% (2/3) | P3 did not notice collapsed log pane |

**Overall first-attempt success rate:** 87% (13/15) — meets aggregate target.

**Time on Task:**

| Task | Target | Mean | Range | Std Dev |
|---|---|---|---|---|
| Launch to server listening | <60s | 38s | 28-52s | 12.2s |
| Add slave + 10 registers | <90s | 62s | 45-85s | 20.8s |
| Set value (decimal) | <10s | 6s | 4-9s | 2.5s |
| Set value (hex) | <15s | 11s | 8-14s | 3.1s |
| Find log entry | <30s | 24s | 12-41s | 15.0s |

All tasks met target times on average. Mean end-to-end workflow: ~141s (vs ~210s Modbus Slave Simulator, ~190s ModScan32 — evaluator-timed, indicative only).

**System Usability Scale:**

| Participant | SUS Score | Adjective Rating |
|---|---|---|
| P1 (QA Engineer) | 72.5 | Good |
| P2 (QA Engineer) | 62.5 | OK/Marginal |
| P3 (Firmware Developer) | 85.0 | Excellent |
| **Mean** | **73.3** | **Good** |

Mean exceeds 68 industry average and 71.4 "Good" boundary (Bangor, Kortum & Miller, 2009).

### Identified Usability Issues

1. **Log pane collapses without visual indicator** (H1, medium severity) — remediation: persistent status bar indicator + minimum visible height.
2. **PLC/Protocol addressing confusion** (H2, medium severity) — remediation: contextual tooltip in RegisterGroupDialog + inline address mode indicator.
3. **No undo for register value edits** (H3, low severity) — deferred to future work.
4. **Incomplete Chinese language pack** (H4, high severity for adoption) — active translation ongoing.

### Threats to Validity

- Small sample size (n=3) limits statistical generalisability; appropriate for formative evaluation.
- All participants from same department — possible selection bias toward above-average Modbus knowledge.
- Comparative timings performed by evaluator (expert), not participants — directional only.
- SUS administered in English with Chinese UI — possible response bias on nuanced items.
- First-contact measurement only — no longitudinal learning curve data.
