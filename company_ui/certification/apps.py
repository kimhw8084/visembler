from __future__ import annotations

from company_ui.components import ButtonIntent, StatusIntent, SelectOption
from company_ui.data_table import ColumnKind, SelectionMode, TableColumn, TableDensity
from company_ui.filters import FilterBarSpec, FilterDefinition, FilterKind
from company_ui.integrations.nicegui_components import ActionButton, Button, IconButton, NumberInput, Panel, Select, StatusBadge, Switch, TextInput
from company_ui.integrations.nicegui_data_table import DataTable
from company_ui.integrations.nicegui_interactions import EmptyState, FilterBar
from company_ui.integrations.nicegui_layout import AppShell
from company_ui.integrations.nicegui_visualization import LineChart
from company_ui.layouts import LayoutSlot
from company_ui.patterns import DataExplorerPage, SettingsPage
from company_ui.visual import Icons
from company_ui.visualization import AxisSpec, AxisType, SeriesSpec, SpecLimits


def build_certification_app() -> AppShell:
    shell = AppShell('Company UI Certification', environment='RC')
    with shell:
        with DataExplorerPage('Equipment Health', 'Integrated Company UI certification scenario') as page:
            with page.slot(LayoutSlot.FILTERS):
                FilterBar(FilterBarSpec(filters=(
                    FilterDefinition('area', 'Area', FilterKind.SELECT, options=('ETCH', 'CVD', 'CMP')),
                    FilterDefinition('tool', 'Tool', FilterKind.SELECT),
                    FilterDefinition('period', 'Period', FilterKind.DATE_RANGE),
                )))
            with page.slot(LayoutSlot.PRIMARY):
                LineChart(
                    'Excursions',
                    (SeriesSpec('excursions', 'Excursions', (2, 5, 3, 8, 4, 6)),),
                    x_axis=AxisSpec(kind=AxisType.CATEGORY, categories=('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat')),
                    spec_limits=SpecLimits(upper=7),
                )
            with page.slot(LayoutSlot.DATA):
                DataTable(
                    rows=(
                        {'id': 'ETCH-021', 'status': 'Critical', 'excursions': 8, 'yield': 96.4},
                        {'id': 'ETCH-014', 'status': 'Watch', 'excursions': 4, 'yield': 98.1},
                    ),
                    columns=(
                        TableColumn('id', 'Tool', ColumnKind.TEXT),
                        TableColumn('status', 'Status', ColumnKind.STATUS),
                        TableColumn('excursions', 'Excursions', ColumnKind.INTEGER),
                        TableColumn('yield', 'Yield', ColumnKind.PERCENT),
                    ),
                    selection=SelectionMode.SINGLE,
                    density=TableDensity.COMPACT,
                    title='Affected equipment',
                )
    return shell


def build_component_gallery() -> AppShell:
    shell = AppShell('Company UI Gallery', environment='RC')
    with shell:
        with SettingsPage('Component Gallery', 'Canonical component states') as page:
            with page.slot(LayoutSlot.PRIMARY):
                with Panel():
                    Button('Secondary')
                    ActionButton('Primary', intent=ButtonIntent.PRIMARY, icon=Icons.SUCCESS)
                    IconButton(Icons.SEARCH, label='Search')
                    StatusBadge('Normal', intent=StatusIntent.SUCCESS, icon=Icons.SUCCESS)
                    StatusBadge('Critical', intent=StatusIntent.DANGER, icon=Icons.WARNING)
                    TextInput('Tool ID', placeholder='ETCH-021')
                    NumberInput('Limit', value=4.2, unit='nm')
                    Select('Area', (SelectOption('etch', 'ETCH'), SelectOption('cvd', 'CVD')))
                    Switch('Auto refresh', value=True)
                    EmptyState('No matching records')
    return shell


def run_certification_app() -> None:
    from nicegui import ui
    build_certification_app()
    ui.run(title='Company UI Certification', reload=False, show=False)


def run_component_gallery() -> None:
    from nicegui import ui
    build_component_gallery()
    ui.run(title='Company UI Gallery', reload=False, show=False)
