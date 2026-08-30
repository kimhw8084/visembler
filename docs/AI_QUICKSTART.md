# Gemma/OpenCode Quick Start

## Before coding

1. Read `AGENTS.md`.
2. Read `AI_CONSTRUCTION_MANIFEST.json`.
3. Identify the dominant user task and select a page pattern from `docs/APP_PATTERNS.md`.
4. Search `FRAMEWORK_CATALOG.json` or `docs/COMPONENT_CATALOG.md` for required capabilities.
5. Inspect the real Python signature before writing the call; `docs/PUBLIC_API_INDEX.md` is a discovery index, not a substitute for source inspection.

## Normal application skeleton

```text
my_app/
├── app.py
├── app_config.py
├── pages/
├── services/
├── repositories/
├── models/
└── tests/
```

Pages compose Company UI. Services implement application logic. Repositories implement SQL/API access. Models carry typed business data.

## Runtime

Use `NiceGUIRuntimeAdapter(RuntimeConfig(...))` instead of importing NiceGUI just to call `ui.run()`.

## Visual construction

Use this order:

```text
registered Page Pattern
  → semantic Layout primitives/slots
    → registered Component/Interaction/Table/Visualization
      → application-specific data and events
```

Do not start from CSS, raw NiceGUI, AG Grid or ECharts.

## After coding

```bash
python -m company_ui.validate .
python -m company_ui.validate . --format json
python -m company_ui.validate . --warnings-as-errors
```

Then run application tests and a startup smoke test. A validator error is not a suggestion; fix it or document a narrow, legitimate escape hatch.
