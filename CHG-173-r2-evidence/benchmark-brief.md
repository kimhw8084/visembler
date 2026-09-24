# Benchmark brief

CHG-173 R2 is an outcome verification on the exact integrated source, with no Product-source/config/test/dependency edits. All report content and datasets below were created or edited through fresh NativeHost runs and supported Report Hub, inspector, Data First, table, presets, history, Preview and export UI actions. Browser automation invoked those controls deterministically. Runtime-owned reports and audit data are copied byte-for-byte; no report model/JSON was edited by hand.

## Five complete report genres

1. Executive KPI/business review: renewal context and risk, Q1–Q4 KPIs, two quarterly trend charts, regional evidence table, budget decision and next step.
2. Semiconductor RCA: WQ-7314 ETCH-08/chamber A, wafer spatial map, before/after yield, SPC trend, distribution evidence, process flow, measures and containment.
3. Experiment decision: randomized control/treatment hypothesis, weekly comparison and distribution, guardrail, assignment evidence, interpretation and staged recommendation.
4. Dense technical operating review: shifts, yield/downtime, SPC, engineering narrative, flow, action table, risk and conditional release.
5. Fresh supply-chain/capacity holdout: new Northstar actuator scenario and week-by-week capacity/demand data, supplier uncertainty table, decision path and allocation recommendation. This data shape was authored for this run and is not the CHG-181 Order/Returns control or a named Product fixture.

The run also remapped the complete Executive source into a new service-reliability incident report, reused a two-chart analytical section, and built the equivalent service incident from blank. It captured explicit source-data-copy mode, ambiguous fields, a target with incompatible/missing role mappings, undo/redo, reload/history, and a competing-edit recovery.

## Starting modes and authoring proof

The first four reports started from governed Report Hub blueprints and were substantively edited. The holdout started from blank, then used Data First, visible component-library insertions and Review Smart composition. The follow-up used guided report/section remap. Logs preserve semantic actions, context changes, modals, insertions, mappings, manual style/layout, undo/redo and persistence points. In this run, guided reuse avoided 25 semantic action events, 10 context switches, 10 manual component insertions and 8 repeated setup/style actions against the blank equivalent. This is run-specific interaction evidence, not a universal speed SLA.
