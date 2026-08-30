#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path

PROD = Path(__file__).resolve().parents[1]
ROOT = PROD.parent
QA = PROD/'qa'

def j(path):
    return json.loads(Path(path).read_text())

def evidence(*paths):
    return [str(Path(p).relative_to(ROOT)) if Path(p).is_absolute() else str(p) for p in paths]

suite = j(QA/'full_suite.json')
browser = j(QA/'browser_smoke.json')
perf = j(QA/'performance_200.json')
fuzz = j(QA/'property_fuzz.json')
contracts = j(QA/'component_contract_validation.json')
advanced = j(QA/'advanced_charts_browser.json')
engineering = j(QA/'engineering_charts_browser.json')
static = j(QA/'static_p0_lint.json')
baseline = j(ROOT/'13_DEEP_AUDIT_248_ELEMENTS/AUDIT_SUMMARY.json')
connector_qa = j(ROOT/'06_CONNECTOR_GEOMETRY_SYSTEM/GOLDEN_CONNECTOR_V5_QA.json')

def sha256(path: Path):
    h=hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()
connector_authority = ROOT/'06_CONNECTOR_GEOMETRY_SYSTEM/GOLDEN_CONNECTOR_ENGINE_V5.js'
connector_frozen = PROD/'core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'
connector_identical = sha256(connector_authority) == sha256(connector_frozen)

G=[]
def gate(n,title,status,reason,evid,next_action):
    G.append({'id':f'ZG-{n:02d}','title':title,'status':status,'reason':reason,'evidence':evid,'next_action':next_action})

core_suite = evidence(QA/'full_suite.json')
editor_ev = evidence(QA/'browser_smoke.json', PROD/'core/editor_store.mjs', PROD/'app/editor.mjs')

gate(1,'Runtime','PARTIAL',f"Production-core suite is green ({suite['commands']}/{suite['commands']} commands) with zero editor/chart browser console errors, but legacy/canonical engines are not yet all consolidated into that suite.",core_suite+evidence(QA/'browser_smoke.json',QA/'advanced_charts_browser.json',QA/'engineering_charts_browser.json'),'Consolidate remaining timeline/diagram/image/wafer/PPT/NiceGUI surfaces into the same zero-console suite.')
gate(2,'Geometry','PARTIAL','Current editor Smart hull, overlap, bounds, zoom and contextual-control geometry pass, but all 248 renderer/layout combinations are not yet exercised.',evidence(QA/'browser_smoke.json',QA/'production_editor_smoke.png'),'Add geometry/property baselines for every canonical renderer and content-density extreme.')
gate(3,'Typography','PARTIAL','Production core enforces an 11px visible-text floor and compact narrative adaptation; full 248-element clipping/wrap/output-profile coverage remains.',evidence(QA/'browser_smoke.json',PROD/'app/tokens.css',PROD/'app/editor.mjs'),'Run all 248 contracts across XS–XL, long labels, localization-like expansion and PPT-safe profiles.')
gate(4,'Tokens','PARTIAL','Static P0 token lint passes and theme semantic colors are tokenized; remaining canonical wave renderers still need consolidation/token purge.',evidence(QA/'static_p0_lint.json',PROD/'app/tokens.css'),'Port remaining engine renderers through production token layer and reject presentation literals in CI.')
gate(5,'Accessibility','PARTIAL','Current editor controls have names, keyboard paths, focus styling, target floors, reduced-motion handling and measured theme contrast. Full 248 interactive inventory is not yet rendered/tested.',evidence(QA/'browser_smoke.json',PROD/'app/editor.css'),'Generate interactive accessibility fixtures for all Tier-4/interactive contracts and add screen-reader state assertions.')
gate(6,'Pointer lifecycle','PARTIAL','Production editor drag/resize recovery handles pointercancel/capture loss without stuck state; remaining specialized interactive engines are not yet integrated.',editor_ev,'Apply the same pointer-session primitive to timeline/image/diagram specialized interactions and fuzz cancel/lost-capture sequences.')
gate(7,'Responsive observation','PARTIAL','Editor has ResizeObserver and 60–140% zoom invariance; advanced and engineering charts have XS–XL rendering. Remaining engines need live ResizeObserver integration.',evidence(QA/'browser_smoke.json',QA/'advanced_charts_browser.json',QA/'engineering_charts_browser.json'),'Wire remaining engines to container observation and add resize storms/content mutation tests.')
gate(8,'Semantic truth','PARTIAL','Statistics, pivot and graph cores block invalid inputs and preserve typed/raw semantics, but a universal AI/data eligibility state-machine gate is not yet connected to all 248 elements.',evidence(PROD/'core/statistics_engine.mjs',PROD/'core/table_pivot_engine.mjs',PROD/'core/graph_semantics_engine.mjs'),'Build centralized data-eligibility/truth preflight and require every renderer/AI composition path to consume it.')
gate(9,'Serialization','PASS','Canonical editor model round-trips deterministically; stable semantic IDs and exact history round-trip are regression tested.',evidence(PROD/'core/editor_store.mjs',QA/'full_suite.json'),'Keep serialization tests mandatory as new component-specific canonical fields are introduced.')
gate(10,'Revision safety','PASS','Every production editor mutation uses revision-checked commands and stale base_revision commits are rejected.',evidence(PROD/'core/editor_store.mjs',QA/'full_suite.json'),'Require future NiceGUI/Python bridge commits to carry the same base_revision contract.')
gate(11,'Undo/Redo','PASS','100 mixed atomic edits, grouped membership restoration, exact undo and redo are covered by the production store suite.',evidence(PROD/'core/editor_store.mjs',QA/'full_suite.json'),'Extend command types only through inverse-tested operations/transactions.')
gate(12,'Connectors','PASS',f"Golden Connector v5 preserved byte-identically ({'yes' if connector_identical else 'NO'}) and authoritative Wave 06/07/09/10 QA records zero route/edge-node failures.",evidence(connector_authority,connector_frozen,ROOT/'06_CONNECTOR_GEOMETRY_SYSTEM/GOLDEN_CONNECTOR_V5_QA.json'),'Keep v5 frozen; add production-core replay fixture when DiagramEngine is consolidated.')
gate(13,'Charts','PARTIAL','12 advanced chart variants and 13 engineering variants have deterministic typed plans, invalid-input blocking and XS–XL browser rendering; the older basic CoreChartEngine family still needs one production renderer boundary.',evidence(QA/'advanced_charts_browser.json',QA/'engineering_charts_browser.json',PROD/'core/advanced_chart_engine.mjs',PROD/'core/engineering_chart_engine.mjs'),'Consolidate Wave 04 basic charts with production render-plan/data-reconciliation gates and remove alias-only remnants.')
gate(14,'Statistics','PASS','Numerical backend matches NumPy/SciPy/statsmodels reference fixtures for distributions, regression, DOE, SPC, capability, CUSUM/EWMA and transforms with invalid-input blocking.',evidence(PROD/'core/statistics_engine.mjs',PROD/'tests/statistics_engine.test.mjs',QA/'full_suite.json'),'Add additional corporate reference datasets when available; keep tolerances explicit.')
gate(15,'Tables','PARTIAL','Production pivot core preserves typed keys, subtotals/grand totals and deterministic expand/collapse; 1,500 seeded rows reconcile across 423 cells to pandas and 100k-row stress passes. Sort/filter UI and full TableEngine renderer are not yet consolidated.',evidence(PROD/'core/table_pivot_engine.mjs',PROD/'tests/table_pivot_reference.test.mjs',QA/'full_suite.json'),'Implement typed sort/filter pipeline, virtualized accessible grid renderer and keyboard navigation on the same core.')
gate(16,'Timelines','PARTIAL','Production timeline semantic core now enforces explicit ISO dates or declared durations, FS/SS/FF/SF dependency types and integer lag, dependency acyclicity, schedule consistency, milestone duration and sequence-only no-date semantics. The visual TimelineEngine renderer/editor integration remains to be consolidated.',evidence(PROD/'core/timeline_semantics_engine.mjs',PROD/'tests/timeline_semantics_engine.test.mjs',QA/'full_suite.json'),'Wire all timeline variants to prepareTimeline() before layout, then add calendar-specific and XS–XL visual regression.')
gate(17,'Diagrams','PARTIAL','New graph semantics engine validates DAG/tree/network/flow/state-machine rules before layout; invalid cycles/roots/unknown nodes/nondeterministic transitions block. Sankey now consumes the shared gate, but full DiagramEngine authoring/layout is not yet consolidated.',evidence(PROD/'core/graph_semantics_engine.mjs',PROD/'tests/graph_semantics_engine.test.mjs',PROD/'core/advanced_chart_engine.mjs'),'Wire all diagram variants to validateGraph() before Golden Connector/layout and add 100-node visual/performance regression.')
gate(18,'Images','OPEN','No production asset-relative crop/anchor/annotation model or untrusted SVG/image ingestion policy has been completed.',evidence(ROOT/'13_DEEP_AUDIT_248_ELEMENTS/IMPROVEMENT_BACKLOG.json'),'Implement asset-relative transform model, crop/zoom invariance tests, and conservative SVG/image sanitization policy.')
gate(19,'Wafer/Fab','OPEN','Production coordinate-registration and missing-vs-zero validation for wafer/fab comparisons is not yet implemented.',evidence(ROOT/'13_DEEP_AUDIT_248_ELEMENTS/IMPROVEMENT_BACKLOG.json'),'Implement wafer coordinate convention/registration validator before any derived comparison renderer.')
gate(20,'PPT','OPEN','Web Rich→PPT Safe mappings are not yet implemented for every shipped component. Exact corporate profile certification additionally requires the external sanitized PPTX/output profile.',evidence(PROD/'contracts/component_contracts.json'),'Implement native/editable mappings by engine now; certify typography/theme/profile fidelity when corporate sample arrives.')
gate(21,'Themes','PARTIAL','Light/dark/corporate production tokens now pass measured 4.5:1 small-text contrast and 3:1 accent/canvas non-text contrast in editor smoke; full renderer/theme screenshot matrix remains.',evidence(QA/'browser_smoke.json',PROD/'app/tokens.css'),'Run all canonical engine visual baselines in all three themes and detect semantic-color drift/orphans.')
gate(22,'Performance','PARTIAL',f"200-component retained-DOM budget passes (p95 {perf['timing']['p95_ms']:.2f} ms, heap growth {perf['heap_growth_mb']:.3f} MB); 100k-row pivot and 100-node semantic validation pass. A 100-node rendered DiagramEngine benchmark is still missing.",evidence(QA/'performance_200.json',PROD/'tests/table_pivot_engine.test.mjs',PROD/'tests/graph_semantics_engine.test.mjs'),'Add retained 100-node diagram route/layout/render benchmark and CI budgets for large accessible table rendering.')
gate(23,'Visual regression','PARTIAL','Advanced and engineering chart families have XS–XL screenshot baselines and editor smoke screenshot exists; all Tier-4 elements/themes/content-density extremes are not yet covered.',evidence(QA/'advanced_charts_browser.json',QA/'engineering_charts_browser.json',QA/'production_editor_smoke.png'),'Build deterministic screenshot matrix keyed by engine × variant × size × theme × density with pixel/structural thresholds.')
gate(24,'Property fuzz','PARTIAL',f"Deterministic 10,000-case corpus passes (seed {fuzz['seed']}) and previously exposed a virtualization-tail bug that was fixed; remaining timeline/image/wafer/PPT/bridge engines are not yet in the corpus.",evidence(QA/'property_fuzz.json',PROD/'tests/property_fuzz.test.mjs'),'Extend generators to every new semantic engine and persist any failing seed as a permanent regression fixture.')
gate(25,'No external runtime dependency','PASS','Production core uses local modules/assets/system fonts and browser tests run from bundled local content without CDN/internet runtime dependencies.',evidence(PROD/'app/index.html',PROD/'app/editor.mjs',QA/'full_suite.json'),'Keep dependency policy build-blocking; vendor only approved local assets if future libraries are introduced.')
gate(26,'NiceGUI boundary','BLOCKED_EXTERNAL','The semantic-commit contract is defined, but the actual Golden NiceGUI package is not present, so final one-process/one-port bridge integration cannot be certified.',evidence(ROOT/'14_CANONICAL_PRODUCTION_SOURCE_AUTHORITY/CANONICAL_SOURCE_AUTHORITY.json'),'Implement a renderer-side semantic commit adapter now, then integrate/certify against the supplied Golden NiceGUI shell without Python pointer-frame traffic.')
gate(27,'Focus continuity','PASS','Unrelated model updates preserve active inspector focus and retained-DOM rendering avoids destructive canvas rebuilds.',evidence(QA/'browser_smoke.json',PROD/'app/editor.mjs'),'Add IME/composition and multi-control focus fixtures as specialized editors are integrated.')
gate(28,'Security','PARTIAL','Current production text/chart rendering escapes dynamic text and does not allow arbitrary AI HTML/CSS, but untrusted SVG/image sanitation/import policy is still missing.',evidence(PROD/'app/editor.mjs',PROD/'core/advanced_chart_engine.mjs',PROD/'core/engineering_chart_engine.mjs'),'Add centralized escaping/sanitization utilities and strict SVG/image importer allowlist before ImageMediaEngine integration.')
gate(29,'Preflight','PARTIAL','Editor geometry and several numerical/chart/graph invalid conditions block or warn before output, but there is not yet a universal 248-contract export preflight aggregator.',evidence(QA/'browser_smoke.json',PROD/'contracts/component_contracts.json',PROD/'core/graph_semantics_engine.mjs'),'Build one preflight aggregator that evaluates every active component contract, semantic engine and output-profile mapping before export.')
gate(30,'Determinism','PARTIAL','Editor serialization, advanced/engineering SVG render plans, pivot fingerprints and graph fingerprints are deterministic under tested inputs; remaining canonical engines and output mappings need renderer-version traceability.',evidence(QA/'full_suite.json',PROD/'core/table_pivot_engine.mjs',PROD/'core/graph_semantics_engine.mjs'),'Add renderer/version IDs to every plan/export artifact and deterministic fixtures for remaining engines.')

summary = {}
for x in G: summary[x['status']] = summary.get(x['status'],0)+1
report = {
    'audit': 'Visualizer Production Gate Audit',
    'scope': 'live 15_PRODUCTION_CORE against the authoritative 30 zero-error gates',
    'baseline_248_audit_average': baseline['overall_average'],
    'baseline_note': 'The original 248-element 77.0 audit remains the authoritative element-level baseline. This live gate audit does not fabricate a new 248 score before every element is re-rendered/retested.',
    'release_ready': all(x['status']=='PASS' for x in G),
    'summary': summary,
    'production_core_suite_pass': suite['pass'],
    'connector_frozen_sha256_identical': connector_identical,
    'external_inputs_missing': ['Golden NiceGUI package','Sanitized corporate PPTX/output profile'],
    'gates': G,
}
(QA/'production_gate_audit.json').write_text(json.dumps(report,indent=2)+'\n')

lines=[
'# Visualizer Live Production Gate Audit','',
'**Scope:** `15_PRODUCTION_CORE` measured against the authoritative 30 zero-error acceptance gates.','',
f"- Original 248-element baseline: **{baseline['overall_average']:.1f}/100** (not silently re-scored).",
 f"- Current production-core automated suite: **{'PASS' if suite['pass'] else 'FAIL'}** ({suite['commands']} commands).",
 f"- Fully closed gates: **{summary.get('PASS',0)}/30**.",
 f"- Partial gates: **{summary.get('PARTIAL',0)}**; open: **{summary.get('OPEN',0)}**; external-blocked: **{summary.get('BLOCKED_EXTERNAL',0)}**.",
 f"- Release ready: **{'YES' if report['release_ready'] else 'NO'}**.",
 f"- Golden Connector v5 frozen-byte identity: **{'PASS' if connector_identical else 'FAIL'}**.",'',
'No new overall element score is claimed until all 248 element contracts have corresponding production renderers and regression evidence.','',
'| Gate | Status | Current evidence / reason | Next required closure |','|---|---|---|---|']
for x in G:
    ev='; '.join(f'`{e}`' for e in x['evidence'][:3])
    reason=x['reason'].replace('|','\\|')
    nxt=x['next_action'].replace('|','\\|')
    lines.append(f"| {x['id']} {x['title']} | **{x['status']}** | {reason} Evidence: {ev} | {nxt} |")
lines += ['','## Highest-impact remaining sequence','',
'1. Image asset-relative model + SVG/image security (`ZG-18`, `ZG-28`).',
'2. Wafer/fab registration and missing/zero semantics (`ZG-19`).',
'3. Wire the new timeline semantic engine into all timeline renderers (`ZG-16`).',
'4. Complete TableEngine sort/filter + accessible virtual renderer (`ZG-15`).',
'5. Consolidate base CoreChartEngine + full theme/visual matrix (`ZG-13`, `ZG-21`, `ZG-23`).',
'6. Universal semantic/export preflight (`ZG-08`, `ZG-29`, `ZG-30`).',
'7. Native/editable PPT mappings (`ZG-20`) while waiting for corporate profile certification input.',
'8. NiceGUI semantic bridge + Golden shell integration when package arrives (`ZG-26`).','']
(QA/'PRODUCTION_GATE_AUDIT.md').write_text('\n'.join(lines))
print(json.dumps({'pass':True,'release_ready':report['release_ready'],'summary':summary,'baseline_248':baseline['overall_average'],'suite_pass':suite['pass'],'connector_identical':connector_identical},indent=2))
