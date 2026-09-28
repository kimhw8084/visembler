# Source authority

Candidate `a095fa229c657a75a136520089194998377c66eb` adds the shared reading-projection policy in `company_ui/products/visualizer/assets/authoring_diagram_studio.mjs`. The candidate source snapshot is included beside this note.

- `connectorTextPadding` at line 309 derives protected horizontal clearance from stroke, marker width, and required CSS-pixel gap.
- `renderCompactDiagramReadingSvg` at line 314 sizes the compact projection using the available width, wrapped label heights, node count, edge topology, edge labels, and marker clearance. It deterministically uses the existing stacked projection when two columns cannot satisfy the policy.
- The compact projection exposes its protected padding, marker envelope, minimum scale, and clearance policy as data attributes for browser measurement.
- `integrated_editor.css` retains the existing 14px medium-label font contract and responsive medium/narrow route selection; it has no product diff in this candidate.
- The shared projection remains consumed by the existing report renderer. No report-specific renderer, graph mutation, node/edge identity mutation, or canonical Diagram Studio editing/rendering changes were introduced.

The exact candidate tree is attached as this carrier commit's sole parent. The source files and tests are included for direct review; repository range is base `28d47acbaab8b493044120f6be4c32a225de4143` to candidate `a095fa229c657a75a136520089194998377c66eb`.
