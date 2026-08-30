"""Canonical Company UI component-gallery source. Run in a NiceGUI 3.15.0 environment."""
from company_ui import (
    AppShell, SettingsPage, LayoutSlot, Panel, Button, ActionButton, ButtonIntent, IconButton,
    TextInput, NumberInput, Select, SelectOption, MultiSelect, Checkbox, Switch, StatusBadge,
    StatusIntent, Alert, FeedbackIntent, EmptyState, TableColumn, ColumnKind, DataTable,
)

def build_gallery():
    shell=AppShell('Company UI Gallery')
    with shell:
        with SettingsPage('Component Gallery','Canonical component states') as page:
            with page.slot(LayoutSlot.PRIMARY):
                with Panel():
                    Button('Secondary')
                    ActionButton('Primary',intent=ButtonIntent.PRIMARY)
                    IconButton('search',label='Search')  # company-ui: allow-ai006
                    StatusBadge('Normal',intent=StatusIntent.SUCCESS)
                    StatusBadge('Critical',intent=StatusIntent.DANGER)
                    TextInput('Tool ID',placeholder='ETCH-021')
                    NumberInput('Limit',value=4.2,unit='nm')
                    Select('Area',(SelectOption('etch','ETCH'),SelectOption('cvd','CVD')))
                    MultiSelect('Status',(SelectOption('watch','Watch'),SelectOption('critical','Critical')))
                    Checkbox('Include held lots')
                    Switch('Auto refresh',value=True)
                    Alert('Data refreshed',intent=FeedbackIntent.SUCCESS)
                    EmptyState('No matching records')
                    DataTable(rows=({'id':'A','status':'Normal'},),columns=(TableColumn('id','ID'),TableColumn('status','Status',ColumnKind.STATUS)))
    return shell
