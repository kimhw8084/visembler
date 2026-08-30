# Company UI v3 Application Platform

## North-star contract

V3 turns Company UI from a governed component framework into an application platform while preserving v2 UI/UX as the compatibility floor. Existing v2 screens remain valid and pixel behavior is not globally rewritten. V3 services are opt-in ownership layers.

## Platform layers

1. **Runtime** owns typed state, atomic transactions, lifecycle, commands, diagnostics and undo/redo.
2. **Data** owns immutable datasets, semantic queries, shared filter sessions and reactive bindings.
3. **Workspace** owns responsive panel geometry, collision rules, persistence and restoration.
4. **Visualization** translates semantic intent into the existing certified visual renderer stack.
5. **Extensions** provide an explicit registration boundary for product-specific capabilities.

## Compatibility law

- Do not replace established v2 renderer anatomy merely to use v3.
- Do not introduce a parallel chart/design system.
- Do not mutate runtime state through untracked mutable references.
- Do not let component-local filters diverge when the component participates in a shared `DataSession`.
- Do not persist workspace state without schema-aware, deterministic restoration.
- Breaking public API changes require a separately governed major-version decision; `3.0.0a1` additions are additive to the inherited root surface.

## Certification boundary

Source completion proves the Python/static/inherited regression contracts. Installed NiceGUI runtime, real 22-route smoke, browser geometry/interaction/console evidence and human visual approval remain target-only gates for stable `3.0.0`.
