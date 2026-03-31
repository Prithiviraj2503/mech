## Step 1: VQMS Workflow Definition

This project is being implemented as a controlled vendor quality workflow, not a simple data-entry form.

### Business goal

The system manages vendor-submitted material certification documents such as Mill Test Certificates and QC reports. Each document must move through a traceable approval pipeline before it can be released to the customer.

### Required workflow

1. Vendor creates a document in `draft`.
2. Vendor submits the document for review.
3. QC validates technical and material values against standards.
4. Purchase validates supplier and commercial compliance.
5. If both approvals pass, the document becomes customer-ready and may be rendered as a PDF.
6. If QC or Purchase rejects it, the vendor must update the same controlled record and resubmit it.

### Core system rules

- The document lifecycle must be state-driven.
- Every approval or rejection must be attributable to a user and timestamp.
- Rejected records must preserve comments for corrective action.
- Final customer PDF access must be blocked until final approval.
- Final approved records must become read-only except for controlled follow-up actions.

### Initial status model

- `draft`
- `submitted`
- `qc_approved`
- `rejected`
- `final_approved`

### Role responsibilities

- `vendor`: creates, edits, submits, and resubmits rejected records.
- `qc`: performs technical review and decides approval or rejection.
- `purchase`: performs final business approval after QC approval.
- `admin`: manages users, reference data, and audit visibility.

### Why this matters

This definition is the contract for the next implementation steps:

- Step 2 adds role-aware authentication.
- Step 3 will add controlled document models.
- Later steps will enforce transitions, review records, notifications, audit logs, and PDF release rules.
