# Issue #13: usability and browser compatibility

## Scope and acceptance

NFR-003 requires a trained inventory operator to add a component in no more than three primary screens. NFR-007 requires core inventory operations to work in the latest stable Chrome, Edge and Firefox releases. This record separates the participant's reported experience from automated compatibility evidence.

The creation task uses an **Admin** account, in line with the existing component-management permissions. The **Staff** role can search inventory, view details and record stock movements; its management restrictions are also tested.

| Acceptance criterion | Evidence |
|---|---|
| Component creation takes at most three primary screens | The acceptance runner records successful HTML responses during the actual browser-driven task and requires exactly Inventory (`/components`) → Add component (`/components/new`) → saved component details. Login is a prerequisite; scrolling and field entry do not add primary screens. |
| Workflow tested by a representative user | Participant report below, provided by the user on 31 October 2026. |
| Latest stable Chrome, Edge and Firefox tested | `scripts/browser_compatibility.py` resolves official vendor stable versions and requires the actual WebDriver browser version to match. See the execution results below and retained `results.json` artifacts. |
| Browser display/functionality issues recorded and fixed | Issue register below, plus per-browser failure reports and screenshots. |
| Results documented | This record, the versioned JSON results and screenshots, and the CI workflow artifacts. |

## Representative-user result

This is a **participant-reported test**, supplied in the project conversation on 31 October 2026. It was not independently observed by the automation. The participant did not supply screenshots or a recording.

| Field | Reported result |
|---|---|
| Participant | Team member familiar with inventory tasks; name not supplied |
| Browser | Chrome 156.0.8078.74, Official Build, 64-bit |
| Screens visited | Inventory → Add component → Component details |
| Number of primary screens | 3 |
| Component saved successfully | Yes |
| Help required | None |
| Usability difficulties | None reported |
| Additional browser observation | Participant also tried Edge and reported that it worked smoothly; Edge version was not supplied. |
| Environment and exact test time | Not supplied |

The reported Chrome test meets the representative-user and three-screen criteria. The additional Edge observation is supplementary and does not establish its exact tested version. Automated stable-browser runs provide independently reproducible version evidence.

## Automated cases

Every browser executes the same cases against a fresh temporary SQLite database, with CSRF enabled and an isolated browser profile:

| Case | Required behavior |
|---|---|
| Authentication, search, combined filters and pagination | Admin sign-in works, search locates a component, and category/supplier/status filters survive navigation to page two. |
| Three-screen creation and keyboard focus | Inventory → form → saved details is recorded from actual HTML responses; Tab moves from SKU to name; all component fields save and the initial Low Stock classification is shown. |
| Component editing | Editing the description persists and returns to component details. |
| Stock operations and history | Stock-in and stock-out produce the expected balances; overselling is rejected without changing stock. |
| CSV inventory import | The template downloads; a mixed CSV creates one component, updates another and rejects an invalid row; the imported stock balance is recorded as an adjustment in history. |
| Category and supplier creation | Visible catalogue forms create usable entries. |
| Filtered reports and downloads | Out-of-stock filtering works; clicking CSV and PDF export downloads nonempty files with the correct signatures. |
| Required fields and layout | Empty required fields prevent submission. Inventory, component form and details have no page-level horizontal overflow at desktop and narrow window sizes; screenshots and measured viewport sizes are retained. Wide tables may scroll within their own containers. |
| Staff workflow and permissions | Staff sign-in, details and stock movement work; component creation/import, user management and availability reports return HTTP 403. |

## Execution results

The original vendor-stable checks passed on **31 October 2026**. On **1 November 2026**, the issue branch was merged with `origin/main` at `62ab85e`, bringing in CSV import, health endpoints, additional service/integration tests and the setup guide. The current acceptance runner also covers the merged CSV workflow and retains WebDriver startup logs.

The merged-code local reruns passed in all three browsers on **1 November 2026**, using Windows 11 and Python 3.14.8. Each completed **seven** workflow groups, the three-screen creation path and six desktop/narrow layout checks. The execution records below are from these merged-code runs.

| Browser | Vendor stable version = actual tested version | Result | Retained execution record |
|---|---|---|---|
| Chrome | 156.0.8078.80 | PASS | [chrome.json](evidence/issue-13/chrome.json) |
| Edge | 156.0.4314.58 | PASS | [edge.json](evidence/issue-13/edge.json) |
| Firefox | 159.0 | PASS | [firefox.json](evidence/issue-13/firefox.json) |

The full merged Python suite passed on 1 November: **170 tests**, 59.91 seconds. The performance acceptance check also passed: 100/100 requests successful, p95 136.71 ms and all requests within two seconds. The earlier 31 October baseline had 92 tests before the latest `main` changes were merged.

Execution records identify the checked-out commit and the runner's SHA-256. A local run may test uncommitted runner changes on top of that commit; the source hash identifies the tested file. CI reruns use their own recorded commit and fresh stable-release resolution.

Desktop and narrow screenshots were inspected for readable labels, available controls, form layout, navigation, and stock/status presentation. No browser-specific application display or functionality defect was found in these exercised workflows. Browser-native select and number-input styling differs; all tested controls remained usable.

Each `results.json` records the start/finish times in UTC, commit, runner hash, OS, Python version, official release metadata URL, expected stable version, actual browser version, user agent, completed cases, primary screens, viewport measurements, screenshots, WebDriver log, Chromium sandbox mode, and failure step/traceback when applicable.

## Issue register

| ID | Finding | Resolution and verification |
|---|---|---|
| COMPAT-001 | The earlier Firefox smoke used Playwright's patched Firefox build, so it did not establish compatibility with the regular latest stable Firefox binary. | Added a Selenium acceptance runner that uses regular vendor releases and rejects version mismatches. Exact pass/fail results are retained per browser. |
| COMPAT-002 | Earlier smoke output did not retain exact versions, screenshots or the observed screen path. | Added JSON evidence, screenshots for the primary screens at desktop/narrow sizes, failure capture, and CI artifact upload on success and failure. |
| HARNESS-001 | An initial oversell test reused the movement selector after a page reload, where its default is Stock In. This was a test setup error, not an application defect. | Explicitly select Stock Out immediately before the oversell attempt. The corrected case passed in all three stable browsers. |
| HARNESS-002 | A merged-code Chrome rerun encountered a stale heading during a sign-in redirect. Linux Edge subsequently returned a generic inspector error while polling a node detached by navigation. | Observe replacement of a per-document JavaScript token, then wait for the new document and expected heading; never query a detached node. Search uses the same navigation wait. Downloads and HTML-validation checks explicitly opt out. |
| ENV-001 | The first regular-Firefox download timed out before starting the browser. | Retried with `SE_TIMEOUT=300`; regular Firefox 159.0 downloaded to the project cache and all cases passed. No application change was needed. |
| CI-001 | [The first Linux CI run](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/actions/runs/41175945964) passed Firefox, unit/performance and setup checks, but Chrome and Edge exited while creating their WebDriver sessions. | The isolated hosted-CI job opts into `ESIMS_CHROMIUM_NO_SANDBOX=1` for its downloaded Chromium browsers. Normal local runs keep their browser sandbox. WebDriver startup logs are now retained for diagnosis; use the updated branch/PR checks as current Linux CI evidence. |

Additional display or functionality failures discovered during these runs must be recorded here with the affected browser/version, reproduction steps, fix and verification result.

## Repeat the automated checks

From PowerShell in the project directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
$env:ESIMS_BROWSER='chrome' # repeat with edge and firefox
.\.venv\Scripts\python.exe scripts/browser_compatibility.py
```

The first run needs network access to read vendor release metadata and download the matching browser/driver. The default Selenium download timeout is 300 seconds. Selenium caches downloads in `instance/selenium-cache`; results go to `instance/browser-evidence/<browser>`. Set `ESIMS_EVIDENCE_DIR` to select another results directory. On Windows, Edge must already be installed; this test does not update the system Edge installation. Linux CI can download the vendor Edge release into its cache.

The CI matrix uses Ubuntu 24.04 and `requirements-browser.txt`, installs browser system libraries, resolves vendor stable releases at run time and retains each browser's evidence for 30 days. The earlier `scripts/browser_acceptance.py` remains an optional Playwright smoke test; it is not the stable-release evidence gate.

## Representative-user procedure for a retest

Use a local/demo inventory with an Admin account and an existing category and supplier. Brief the participant on SKU uniqueness, quantity and reorder threshold. Start on Inventory after login. Ask the participant to add a component with a unique SKU, quantity 3, threshold 5 and price 19.50, then confirm the saved details and Low Stock status. Record the actual screen sequence, success/failure, help needed, confusing controls, browser/version, environment and any defects. Do not replace an unsuccessful or incomplete human result with an automated pass.

## Sources

- [Issue #13](https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System/issues/13) and its acceptance criteria.
- [Selenium Manager browser/version management](https://www.selenium.dev/documentation/selenium_manager/).
- [Playwright's documented Firefox patches](https://playwright.dev/python/docs/browsers#firefox).
- Official stable metadata: [Chrome](https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json), [Edge](https://edgeupdates.microsoft.com/api/products?view=enterprise), [Firefox](https://product-details.mozilla.org/1.0/firefox_versions.json).
