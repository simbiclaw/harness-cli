# annual-report-submission — L2 Capsule Bone

Top-loaded operator map for the annual report submission domain. This is the Bone — the structural scaffold. Flesh (`ui_step` definitions) lives in sibling files.

## Domain context

Customers contact support regarding annual report filing with Companies House. Common scenarios: late filing due to system errors, confusion about deadlines, penalty disputes, and extension requests.

## Operators

### verify-system-status

- **Intent**: Customer claims the online system prevented timely filing.
- **Trigger**: Customer mentions "couldn't file", "system was down", "website error", or similar.
- **Preconditions**: Customer has an active company registration.
- **Steps**:
  1. `ui_binding_ref: "collect-filing-date"`
  2. `ui_binding_ref: "check-system-status"`
  3. `ui_binding_ref: "collect-error-evidence"`
  4. `ui_binding_ref: "confirm-alternative-methods"`
- **Terminal state**: Evidence collected; late filing accepted with system-failure annotation.

### explain-deadline

- **Intent**: Customer is confused about the filing deadline.
- **Trigger**: Customer asks "when is the deadline" or "am I late".
- **Preconditions**: Customer's company type and accounting reference date are known.
- **Steps**:
  1. `ui_binding_ref: "identify-company-type"`
  2. `ui_binding_ref: "calculate-deadline"`
  3. `ui_binding_ref: "confirm-filing-status"`
- **Terminal state**: Customer understands deadline and whether they are late.

### handle-penalty-appeal

- **Intent**: Customer wants to appeal a late filing penalty.
- **Trigger**: Customer mentions "penalty", "fine", "appeal".
- **Preconditions**: A penalty has been issued.
- **Steps**:
  1. `ui_binding_ref: "verify-penalty-details"`
  2. `ui_binding_ref: "collect-grounds-for-appeal"`
  3. `ui_binding_ref: "submit-appeal"`
- **Terminal state**: Appeal submitted or customer informed of appeal requirements.
