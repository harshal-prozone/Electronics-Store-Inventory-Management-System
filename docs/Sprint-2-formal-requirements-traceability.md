# Sprint 2 requirements / design / test traceability review

> Engineering mapping, **not formal acceptance or a pass sheet**. The original combined PDF remains authoritative; its documents and initial RTM have not been altered. No authorized reviewer decision is recorded.

## Source control

- `ESIMS-2026-G07_SRS_SAD_STP .pdf`, SHA-256 `311729bf2d507b550ccc8005dd25785c7421f9c78c60dd1919e7babf57e6e81f` (55 PDF pages). SRS requirements are on PDF pages 11–13; SAD §3.8 on PDF page 27; STP §13.2 on PDF pages 47–48. Page references here are PDF viewer numbers, not printed section page numbers.
- `Software Requirements Specification.pdf`, SHA-256 `d907d9bf37289aff82ed86952001b4a32393d1149d4f669eef0e3704ef2ee135`. The combined PDF supplies the wording and matrices below. Document approval and reviewer/date have not been established.

## Requirement-to-design-to-test matrix

Requirement text is transcribed from SRS §§5–7 with PDF line breaks normalized to spaces; original wording and IDs are preserved. The design references and representative original case IDs come from SAD §3.8. For the complete original case lists consult STP §13.2; case-level gap classifications and evidence are in [Original STP reconciliation](Original-STP-reconciliation.md). Actual Flask implementation, gaps, and evidence are indexed per requirement in [architecture reconciliation](Architecture-and-baseline-reconciliation.md). None of these links establish original-case passes, design approval or a waiver.

| ID | Original SRS requirement | PDF page | Original SAD component (§3.8) | Representative original cases (§3.8) |
|---|---|---:|---|---|
| FR-001 | The system shall allow an administrator to create a user account with a unique username / email. | 11 | AUTH-02 | UT-USR-01, ST-USR-01 |
| FR-002 | The system shall authenticate a user by username / email and password before granting access. | 11 | AUTH-01 | UT-AUTH-01, ST-AUTH-01 |
| FR-003 | The system shall enforce role-based access so that Staff cannot perform Administrator-only actions. | 11 | AUTH-02 | IT-USR-01, ST-SEC-01 |
| FR-004 | The system shall allow an authenticated user to add a component with name, SKU, category, supplier, unit price, quantity and reorder level. | 11 | INV-01 | UT-INV-01, ST-INV-01 |
| FR-005 | The system shall reject a component whose SKU / code is not unique. | 11 | INV-01 | UT-INV-02, IT-INV-01 |
| FR-006 | The system shall allow a user to edit the details of an existing component. | 11 | INV-01 | UT-INV-07, ST-INV-03 |
| FR-007 | The system shall allow an administrator to delete (soft-delete) a component. | 11 | INV-01 | UT-INV-11, ST-INV-05 |
| FR-008 | The system shall display a paginated, searchable list of components with current quantity and availability status. | 11 | INV-01 | IT-INV-11, ST-INV-02 |
| FR-009 | The system shall allow filtering of components by category, supplier and availability status. | 11 | INV-01 | UT-INV-16, ST-INV-02 |
| FR-010 | The system shall allow a user to record a stock-in transaction that increases a component's quantity. | 11 | STK-01 | UT-STK-03, ST-STK-01 |
| FR-011 | The system shall allow a user to record a stock-out transaction and shall prevent a component's quantity from going below zero. | 11 | STK-01 | UT-STK-01, IT-STK-01 |
| FR-012 | The system shall automatically set availability to “Low Stock” when quantity ≤ reorder level and “Out of Stock” when quantity = 0. | 11 | STK-02 | UT-STK-02, ST-STK-01 |
| FR-013 | The system shall allow an administrator to add, edit and delete categories. | 11 | CAT-01 | UT-CAT-01, ST-CAT-01 |
| FR-014 | The system shall allow an administrator to add, edit and delete suppliers. | 11 | CAT-01 | UT-SUP-01, ST-CAT-01 |
| FR-015 | The system shall generate an availability report of components, filterable by category, supplier and status. | 11 | RPT-01 | UT-RPT-01, ST-RPT-01 |
| FR-016 | The system shall allow the availability report to be exported as CSV and / or PDF. | 11 | RPT-01 | UT-RPT-03, ST-RPT-01 |
| FR-017 | The system shall display a dashboard showing total components, total stock value, low-stock count and out-of-stock count, with at least one chart. | 11 | DSH-01 | UT-DSH-02, ST-DSH-01 |
| FR-018 | The system shall record every stock transaction with component, type, quantity, user and timestamp. | 11 | STK-01 | IT-STK-01, ST-STK-01 |
| FR-019 | The system shall log security-relevant events and deletions in an audit log. | 12 | AUD-01 | IT-AUTH-03, ST-SEC-04 |
| NFR-001 | 95% of inventory list / search requests shall respond within 2 seconds for a catalogue of up to 5,000 components under the defined test load. | 13 | CORE-01, DB-01 | PERF-01 |
| NFR-002 | The application shall be available at least 99% during store operating hours, excluding planned maintenance. | 13 | CORE-01 | ST-NFR-03 |
| NFR-003 | A trained staff member shall be able to add a new component in no more than 3 primary screens. | 13 | UI-01 | ST-NFR-02 |
| NFR-004 | Concurrent stock-out transactions shall never reduce a component's quantity below zero. | 13 | STK-01 | IT-STK-02 |
| NFR-005 | Business logic shall be organized into identifiable modules / services with automated unit tests. | 13 | all apps | ST-NFR-04 |
| NFR-006 | The system shall support at least 5,000 components and 10 concurrent users without functional degradation. | 13 | DB-01 | PERF-01 |
| NFR-007 | The web UI shall function on the latest versions of Chrome, Edge and Firefox. | 13 | UI-01 | ST-NFR-01 |
| NFR-008 | Core services shall expose testable interfaces independent of the UI. | 13 | all apps | UT-STK-02, ST-NFR-04 |
| SEC-001 | Passwords shall be stored only as salted hashes, never as plaintext. | 13 | AUTH-01 | UT-AUTH-03, ST-SEC-03 |
| SEC-002 | Role-based access shall prevent Staff from accessing Administrator functions (delete, user management). | 13 | AUTH-02 | IT-INV-07, ST-SEC-01 |
| SEC-003 | The system shall validate and sanitize all user-supplied input to prevent SQL injection and XSS. | 13 | CORE-01 | IT-INV-12, ST-SEC-03 |
| SEC-004 | Authenticated sessions / tokens shall expire, and invalid or expired credentials shall be rejected. | 13 | AUTH-01 | IT-AUTH-02, ST-SEC-05 |
| SEC-005 | State-changing requests shall be protected against CSRF. | 13 | CORE-01 | IT-SEC-01, ST-SEC-02 |
| SEC-006 | Security-relevant events (failed login, unauthorized access, deletions) shall be logged. | 13 | AUD-01 | IT-AUTH-03, ST-SEC-04 |

## Review and coverage

- 33 numbered SRS requirements (19 FR, 8 NFR, 6 SEC) have original design and representative test references above; this count does not include the additional business rules and field-layout requirements in SRS §§8–9. Those remain authoritative and must also be evaluated.
- **Original execution/acceptance:** not established; the source STP initially marked its cases N. Related Flask tests do not automatically execute or pass original Django/DRF/PostgreSQL cases. The 99-case reconciliation is a gap assessment, not a result sheet.
- **Design and deviation approval:** not recorded. Approval of the alternate implementation, its architecture and unresolved gaps requires an authorized reviewer; this table cannot grant it.

## Reviewer decision

- [ ] Complete — every requirement has an approved design and test/evidence mapping.
- [ ] Complete with accepted deviations — all deviations are explicitly approved and linked.
- [ ] Incomplete — unresolved mapping, test, or evidence gaps remain.

Reviewer name / role: **not recorded**

Reviewer approval link or signature: **not recorded**

Review date: **not recorded**
