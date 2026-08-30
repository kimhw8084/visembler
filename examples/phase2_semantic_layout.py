"""Phase 2 semantic layout example.

This example is intentionally business-component-light. Phase 3+ replaces the
placeholder NiceGUI labels with approved company components while preserving the
same shell and layout grammar.
"""

from company_ui import (
    AppShell, Breadcrumb, DataExplorerPage, Grid, GridPreset, LayoutSlot,
    NavigationModel, NavItem, NavSection, Section,
)

navigation = NavigationModel((
    NavSection('workspace', 'Workspace', (
        NavItem('equipment', 'Equipment Health', '/equipment', icon='monitor_heart'),
        NavItem('investigations', 'Investigations', '/investigations', icon='manage_search'),
    )),
    NavSection('operations', 'Operations', (
        NavItem('monitoring', 'Live Monitoring', '/monitoring', icon='monitoring'),
        NavItem('settings', 'Settings', '/settings', icon='settings'),
    )),
))


def build_page() -> None:
    from nicegui import ui

    with AppShell('Process Intelligence', navigation, active_route='/equipment', environment='prod'):
        with DataExplorerPage(
            'Equipment Health',
            'Current excursion exposure and affected material.',
            breadcrumbs=(Breadcrumb('Manufacturing'), Breadcrumb('Equipment Health')),
        ) as page:
            with page.slot(LayoutSlot.FILTERS):
                ui.label('Phase 3 FilterBar goes here')
            with page.slot(LayoutSlot.METRICS):
                with Grid(GridPreset.METRICS):
                    for label in ('Affected Lots', 'Critical Tools', 'Excursions', 'Median Response'):
                        ui.label(label)
            with page.slot(LayoutSlot.PRIMARY):
                ui.label('Phase 6 ChartPanel goes here')
            with page.slot(LayoutSlot.DATA):
                ui.label('Phase 5 DataTable goes here')


if __name__ in {'__main__', '__mp_main__'}:
    from nicegui import ui
    build_page()
    ui.run()
