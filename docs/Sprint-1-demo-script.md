# One-minute Sprint 1 demo recording plan

**Important:** This is a timed storyboard, not a recorded video. Record the working application with real data, check that text is legible, and upload the actual video file to the repository.

## 60-second run of show

| Time | Demonstration | Narration cue |
|---|---|---|
| 0-5 s | Show the ESIMS application and sign in as an authorised Admin. | "This is the Electronics Store Inventory Management System." |
| 5-15 s | Open inventory; search for a component, change a filter, and show pagination if useful. | "The inventory list supports search and filtering." |
| 15-25 s | Open a component and show quantity, reorder level, and current availability. | "Availability is derived from current quantity and its reorder threshold." |
| 25-38 s | Perform a stock-in or stock-out and show the resulting quantity and movement record. | "Every stock movement is recorded, and stock-out cannot exceed available quantity." |
| 38-48 s | Show category/supplier management if the merged version is available; otherwise skip this segment rather than showing an unmerged branch as delivered. | "Administrators can maintain catalogue values used by components." |
| 48-57 s | Open the availability report, apply filters, and download one export format. | "The report uses the selected filters for export." |
| 57-60 s | End on the resulting inventory/report page. | "This is the working Sprint 1 build." |

## Recording checklist

- Start with the app already running and a dedicated demo database populated with non-sensitive sample data.
- Keep the cursor and text visible; avoid long waits, terminal setup or credential exposure.
- Demonstrate one real successful workflow, not a slide deck or simulated UI.
- Confirm that stock movement history changes after the adjustment.
- If category/supplier pages or reports are not merged and running, do not present them as part of the delivered `main` build.
- Upload the actual MP4/WebM file through GitHub after recording; use a clear name such as `docs/demo/sprint-1-demo.mp4`.
