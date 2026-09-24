# Remap presentation behavior

The compatibility decision remains owned by the reusable analytical binding/remap contract. This presentation exposes its result without changing mapping, recipe, transform, copy, or apply semantics.

- A shared dataset slot presents its common Data source and common field requirements once, with a concise dependent-visual count. Per-visual controls appear only where the requirements differ.
- Fields use product labels such as Category, Measurement, Time, Reference, Affected, and Tool.
- Ambiguous and incompatible mappings have one concise summary and targeted field messages; the reason a choice is blocked remains visible. Apply stays disabled until required choices are valid.
- The dialog remains keyboard-operable. Field changes restore focus, and Escape returns to the invoking flow.
- Atomic apply, source-data immutability, destination dataset identity, source-copy mode, undo/redo, reload, history and conflict recovery are recorded in the candidate-bound remap receipt.

The final acceptance receipt reports two dependent visuals, three distinct shared-slot field controls, restored focus, zero manual values re-entered for new data, and no stale source dataset identity in the destination. The ambiguous and incompatible cases remain fail-closed until resolved.
