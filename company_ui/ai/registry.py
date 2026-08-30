from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from company_ui.ai.models import AiConstructionDefinition
from company_ui.components.registry import COMPONENT_REGISTRY
from company_ui.content.registry import CONTENT_REGISTRY
from company_ui.convenience_registry import CONVENIENCE_REGISTRY
from company_ui.data_table.registry import TABLE_REGISTRY
from company_ui.engineering.registry import ENGINEERING_REGISTRY
from company_ui.interaction_registry import INTERACTION_REGISTRY
from company_ui.jobs import JOB_REGISTRY
from company_ui.patterns.registry import PATTERN_REGISTRY
from company_ui.performance import PERFORMANCE_REGISTRY
from company_ui.runtime.registry import RUNTIME_REGISTRY
from company_ui.security.registry import SECURITY_REGISTRY
from company_ui.visual.registry import ICON_REGISTRY, ILLUSTRATION_REGISTRY
from company_ui.visualization.registry import VISUALIZATION_REGISTRY

_ITEMS = {
    'page_pattern': AiConstructionDefinition(
        'page_pattern', 'A new page or application screen is requested.', 'company_ui.patterns.*',
        'PATTERN_REGISTRY / docs/APP_PATTERNS.md', 'Freehand page composition with raw NiceGUI layout.',
        'Page patterns own information hierarchy and responsive transformations.'),
    'layout': AiConstructionDefinition(
        'layout', 'A page needs columns, stacks, split panes, inspectors or responsive rearrangement.', 'company_ui.layouts.*',
        'docs/LAYOUT_RULES.md', 'ui.row/ui.column/ui.grid or arbitrary CSS geometry.',
        'Semantic layout primitives preserve approved spacing and breakpoints.'),
    'component': AiConstructionDefinition(
        'component', 'A button, input, status, surface or basic control is needed.', 'company_ui components/integrations',
        'COMPONENT_REGISTRY / docs/COMPONENT_CATALOG.md', 'Raw ui.button/ui.input/ui.select or custom control styling.',
        'Framework components own visual states, accessibility, density and theme behavior.'),
    'content': AiConstructionDefinition(
        'content', 'Metrics, detail/property presentation, hierarchy, viewers, workflow steps, comparisons, search results or command UI are needed.', 'company_ui.content + integrations',
        'CONTENT_REGISTRY / docs/COMPONENT_CATALOG.md', 'Ad-hoc KPI cards, property markup, raw tree/viewer/stepper composition or custom command modals.',
        'Content primitives complete the common enterprise UI vocabulary while inheriting Company UI accessibility and design laws.'),
    'form_filter_overlay': AiConstructionDefinition(
        'form_filter_overlay', 'Forms, analytical filters, dialogs, drawers, menus or feedback are needed.', 'company_ui.forms/filters/overlays/feedback',
        'INTERACTION_REGISTRY / docs/RECIPES.md', 'Ad-hoc modal/drawer/toast markup.',
        'The interaction grammar defines when each surface is appropriate and how it behaves.'),
    'table': AiConstructionDefinition(
        'table', 'Rows/columns, records, selection, editing or large datasets are required.', 'company_ui.data_table + integrations.DataTable',
        'TABLE_REGISTRY / docs/COMPONENT_CATALOG.md', 'Raw ui.aggrid or manually rendered HTML tables.',
        'The DataTable subsystem owns enterprise interaction, persistence and server-side contracts.'),
    'visualization': AiConstructionDefinition(
        'visualization', 'A chart, trend, distribution, Pareto, control chart or spatial analysis is required.', 'company_ui.visualization',
        'VISUALIZATION_REGISTRY / docs/COMPONENT_CATALOG.md', 'Raw ui.echart, arbitrary palettes or per-app ECharts styling.',
        'The chart layer owns theme, grammar, cross-filter behavior and engineering annotations.'),
    'visual_asset': AiConstructionDefinition(
        'visual_asset', 'An icon, state illustration or dataviz marker is required.', 'Icons.*, Illustrations.*, visual registries',
        'ICON_REGISTRY / docs/ICON_CATALOG.md', 'Emoji, downloaded SVGs or arbitrary icon-name strings.',
        'Canonical semantic assets make recognition deterministic and keep the package offline.'),
    'state_async': AiConstructionDefinition(
        'state_async', 'Persistence, URL state, long-running work, refresh, debounce, cancellation or shortcuts are needed.', 'company_ui.state/async_tools/services',
        'CONVENIENCE_REGISTRY / docs/RECIPES.md', 'Direct app.storage manipulation, custom timers or duplicate async logic.',
        'Convenience primitives prevent stale results, duplicate work and inconsistent persistence.'),
    'jobs': AiConstructionDefinition(
        'jobs', 'Work must outlive a request or may need restart-survivable execution.', 'company_ui.jobs',
        'JOB_REGISTRY / docs/PERFORMANCE_GUIDE.md', 'Raw asyncio.create_task for business-critical long work.',
        'The durable-job contract lets app code move from in-process tasks to a company scheduler without UI rewrites.'),
    'engineering': AiConstructionDefinition(
        'engineering', 'Semiconductor entities, limits, affected/control comparison, commonality, evidence or RCA are needed.', 'company_ui.engineering',
        'ENGINEERING_REGISTRY / docs/COMPONENT_CATALOG.md', 'Reinvented domain status/limits or causal claims from simple overlap.',
        'Domain primitives preserve analytical semantics and evidence/causality boundaries.'),
    'performance': AiConstructionDefinition(
        'performance', 'Repeated data work, large local tables, hidden expensive content or backend fan-out needs optimization.', 'company_ui.performance',
        'PERFORMANCE_REGISTRY / docs/PERFORMANCE_GUIDE.md', 'Ad-hoc caches, raw background threads, speculative retries or app-specific performance layers.',
        'Performance primitives are bounded, measured, cancellation-aware and documented with explicit avoid-when rules.'),
    'security_runtime': AiConstructionDefinition(
        'security_runtime', 'Authentication, permissions, uploads, logging, proxying, health or deployment are involved.', 'company_ui.security/runtime/diagnostics',
        'SECURITY_REGISTRY + RUNTIME_REGISTRY + docs/COMPANY_ENVIRONMENT.md', 'Page-local auth checks, trusted headers without validation, raw secrets or improvised proxy settings.',
        'Security and deployment must remain fail-closed and centrally configurable.'),
    'certification': AiConstructionDefinition(
        'certification', 'A release is being promoted from Production Gold Candidate to Company Production Gold.', 'company_ui.certification',
        'company-ui-gold-certify / docs/GOLD_PROMOTION_HARNESS.md', 'Manual sign-off without machine-readable evidence or checking HTTP while ignoring WebSocket/browser/runtime behavior.',
        'Gold promotion is an evidence-producing gate and must fail closed when any required company-runtime probe fails or is skipped.'),
}

AI_CONSTRUCTION_REGISTRY: Mapping[str, AiConstructionDefinition] = MappingProxyType(_ITEMS)

FRAMEWORK_REGISTRY_COUNTS = MappingProxyType({
    'components': len(COMPONENT_REGISTRY),
    'content': len(CONTENT_REGISTRY),
    'page_patterns': len(PATTERN_REGISTRY),
    'interactions': len(INTERACTION_REGISTRY),
    'tables': len(TABLE_REGISTRY),
    'visualizations': len(VISUALIZATION_REGISTRY),
    'engineering': len(ENGINEERING_REGISTRY),
    'security': len(SECURITY_REGISTRY),
    'runtime': len(RUNTIME_REGISTRY),
    'convenience': len(CONVENIENCE_REGISTRY),
    'performance': len(PERFORMANCE_REGISTRY),
    'jobs': len(JOB_REGISTRY),
    'icons': len(ICON_REGISTRY),
    'illustrations': len(ILLUSTRATION_REGISTRY),
})


def get_ai_construction(key: str) -> AiConstructionDefinition:
    try:
        return AI_CONSTRUCTION_REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f'Unknown AI construction category: {key}') from exc
