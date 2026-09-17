"""Maintained browser measurement contracts for promoted WaferFab visuals."""

WAFERFAB_RENDERER_CONTRACTS = {
    'Wafer Map': {
        'id': 'wafer-map',
        'renderer': 'cs-wafer-svg',
        'area_selector': '.cs-wafer-svg>circle,.cs-wafer-svg [data-wafer-die]',
        'mark_selector': '.cs-wafer-svg [data-wafer-die]',
    },
    'Wafer Difference Map': {
        'id': 'wafer-difference',
        'renderer': 'cs-wafer-svg.cs-wafer-difference',
        'area_selector': '.cs-wafer-svg.cs-wafer-difference',
        'mark_selector': '.cs-wafer-svg.cs-wafer-difference [data-wafer-die]',
    },
    'Tool × Chamber Matrix': {
        'id': 'tool-chamber-matrix',
        'renderer': 'cs-fab-matrix',
        'area_selector': '.cs-fab-matrix',
        'mark_selector': '.cs-fab-matrix [data-chart-point]',
    },
    'Golden vs Affected Profile': {
        'id': 'golden-affected-profile',
        'renderer': 'cs-fab-profile',
        'area_selector': '.cs-fab-profile',
        'mark_selector': '.cs-fab-profile circle',
    },
    'Control vs Affected Distribution': {
        'id': 'control-affected-distribution',
        'renderer': 'cohort box marks',
        'area_selector': '.chart-studio-control-vs-affected-distribution .cs-chart-svg',
        'mark_selector': '.chart-studio-control-vs-affected-distribution .cs-chart-svg rect[fill-opacity]',
    },
}

LEGACY_WAFERFAB_SELECTOR = '.cs-wafer-svg>circle,.cs-wafer-svg [data-wafer-die]'
