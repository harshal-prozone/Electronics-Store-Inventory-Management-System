# Issue #13 — representative-user acceptance record

**Purpose:** retain auditable human evidence for the three-primary-screen component-creation task. Automated browser tests are separate evidence and do not replace this record.

## Session details

- Participant identifier or role (use a code if anonymity is required):
- Confirmation participant is representative of an inventory operator:
- Facilitator:
- Date:
- Start/end time and timezone:
- Host OS/device:
- Browser name and exact version:
- Viewport dimensions:
- Application commit:
- Test database / sample component identifier (non-sensitive):
- Consent to retain screenshots/recording (if applicable):

## Task

Ask the participant to create the prepared sample component using the normal UI. Do not coach them unless the protocol explicitly allows it.

Required primary-screen path:
1. Inventory (`/components`)
2. Add component (`/components/new`)
3. Saved component details

Login is a prerequisite. Scrolling and field entry do not count as additional primary screens.

## Observed result

- Number of primary screens visited:
- Component saved successfully (yes/no):
- Time to completion:
- Help/prompts required:
- Errors encountered:
- Participant-reported difficulties:
- Participant comments (quote or paraphrase accurately):
- Screenshots/video evidence path:
- Observer notes:

## Browser compatibility observations

Record exact browser versions separately for any additional manual checks. Automated stable-browser evidence is retained in `docs/Issue-13-usability-compatibility.md` and CI artifacts; do not substitute an unversioned statement such as “worked smoothly.”

## Conclusion

- [ ] PASS — completed independently in no more than three primary screens.
- [ ] PASS WITH ISSUES — task completed but usability issues were observed.
- [ ] FAIL — task not completed or exceeded the screen limit.

- Facilitator:
- Participant acknowledgement (if appropriate):
- Date:
- Evidence artifact links:

Do not invent participant details, environment metadata, timestamps, screenshots, or results.
