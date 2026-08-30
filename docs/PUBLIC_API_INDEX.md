# Company UI Public API Index

Framework version: `3.0.0a1`  
NiceGUI runtime: `3.15.0`  
Frozen root exports: **809**

Generated from `PUBLIC_API_CONTRACT.json`. The JSON contract—not this rendered table—is authoritative for compatibility checks.

| Symbol | Kind | Owning module | Signature |
|---|---|---|---|
| `AI_CONSTRUCTION_REGISTRY` | constant | `builtins` | `` |
| `AccessDecision` | class | `company_ui.security.models` | `(allowed: "'bool'", reason: "'str'", missing_permissions: "'tuple[str, ...]'" = (), missing_roles: "'tuple[str, ...]'" = ()) -> 'None'` |
| `AccessPolicy` | class | `company_ui.security.models` | `(required_permissions: "'frozenset[str]'" = frozenset({}), any_permissions: "'frozenset[str]'" = frozenset({}), required_roles: "'frozenset[str]'" = frozenset({}), any_roles: "'frozenset[str]'" = frozenset({}), allow_anonymous: "'bool'" = False) -> 'None'` |
| `Accordion` | class | `company_ui.integrations.nicegui_components` | `(title: "'str'", open: "'bool'" = False)` |
| `ActionButton` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", intent: "'ButtonIntent'" = 'primary', size: "'ComponentSize'" = 'medium', icon: "'str \| None'" = None, disabled: "'bool'" = False, loading: "'bool'" = False, full_width: "'bool'" = False, success_message: "'str \| None'" = None, error_message: "'str \| None'" = None, on_click: "'Callable[..., Any] \| None'" = None) -> "'None'"` |
| `ActionButtonSpec` | class | `company_ui.components.models` | `(label: "'str'", intent: "'ButtonIntent'" = 'secondary', size: "'ComponentSize'" = 'medium', icon: "'str \| None'" = None, disabled: "'bool'" = False, loading: "'bool'" = False, full_width: "'bool'" = False, aria_label: "'str \| None'" = None, success_message: "'str \| None'" = None, error_message: "'str \| None'" = None, prevent_duplicate: "'bool'" = True) -> 'None'` |
| `ActionMenu` | class | `company_ui.integrations.nicegui_interactions` | `(items: "'Sequence[MenuItemSpec]'")` |
| `ActionRow` | class | `company_ui.layouts.primitives` | `()` |
| `ActiveFilter` | class | `company_ui.filters.models` | `(key: "'str'", label: "'str'", display_value: "'str'", value: "'object'", removable: "'bool'" = True) -> 'None'` |
| `ActivityDrawer` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", subtitle: "'str \| None'" = None, side: "'DrawerSide'" = 'right', size: "'OverlaySize'" = 'medium', dismissible: "'bool'" = True, resizable: "'bool'" = False, persistent: "'bool'" = False)` |
| `ActivityFeed` | class | `company_ui.integrations.nicegui_content` | `(items: "'Sequence[ActivityItem]'", empty_message: "'str'" = 'No recent activity')` |
| `ActivityItem` | class | `company_ui.content.models` | `(key: "'str'", title: "'str'", timestamp: "'str \| None'" = None, detail: "'str \| None'" = None, icon: "'str \| None'" = None, intent: "'StatusIntent'" = 'neutral', actor: "'str \| None'" = None) -> 'None'` |
| `AdvancedFilterDrawer` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", subtitle: "'str \| None'" = None, side: "'DrawerSide'" = 'right', size: "'OverlaySize'" = 'medium', dismissible: "'bool'" = True, resizable: "'bool'" = False, persistent: "'bool'" = False)` |
| `Aggregation` | class | `company_ui.data_engine.models` | `(*values)` |
| `Alert` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", message: "'str \| None'" = None, intent: "'FeedbackIntent'" = 'info', dismissible: "'bool'" = False)` |
| `AlertSpec` | class | `company_ui.feedback.models` | `(title: "'str'", message: "'str \| None'" = None, intent: "'FeedbackIntent'" = 'info', dismissible: "'bool'" = False, action_label: "'str \| None'" = None) -> 'None'` |
| `AlertStack` | class | `company_ui.layouts.primitives` | `()` |
| `Align` | class | `company_ui.layouts.models` | `(*values)` |
| `AnalysisWorkspacePage` | class | `company_ui.patterns.pages` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ()) -> "'None'"` |
| `AnalyticalDataController` | class | `company_ui.performance.analytics` | `(loader: "'Callable[[Any], T \| Awaitable[T]]'", debounce_seconds: "'float'" = 0.15, cache_ttl_seconds: "'float'" = 60, cache_size: "'int'" = 64, monitor: "'PerformanceMonitor \| None'" = None)` |
| `AnalyticalDataState` | class | `company_ui.performance.analytics` | `(status: "'DataLoadStatus'" = 'idle', data: "'T \| None'" = None, error: "'BaseException \| None'" = None, stale: "'bool'" = False, duration_ms: "'float \| None'" = None) -> 'None'` |
| `AnnotationIntent` | class | `company_ui.visualization.models` | `(*values)` |
| `AppHeader` | class | `company_ui.integrations.nicegui_layout` | `(title: "'str'", subtitle: "'str \| None'" = None, environment: "'str \| None'" = None, greeting: "'str \| None'" = None, user_name: "'str \| None'" = None, user_initials: "'str'" = 'U', on_settings: "'Callable[[], None] \| None'" = None, on_about: "'Callable[[], None] \| None'" = None, on_mobile_navigation: "'Callable[[], None] \| None'" = None)` |
| `AppInfoDialog` | class | `company_ui.integrations.nicegui_layout` | `(app_name: "'str'", version: "'str'", environment: "'str \| None'" = None, framework_version: "'str'" = '3.0.0a1')` |
| `AppShell` | class | `company_ui.integrations.nicegui_layout` | `(title: "'str'", navigation: "'NavigationModel \| None'" = None, active_route: "'str \| None'" = None, sidebar: "'SidebarMode'" = 'auto', environment: "'str \| None'" = None, on_navigate: "'Callable[[str], None] \| None'" = None, subtitle: "'str \| None'" = None, greeting: "'str \| None'" = None, user_name: "'str \| None'" = None, user_initials: "'str'" = 'U', on_settings: "'Callable[[], None] \| None'" = None, on_about: "'Callable[[], None] \| None'" = None, on_logout: "'Callable[[], None] \| None'" = None, owner: "'str \| None'" = None, on_support: "'Callable[[], None] \| None'" = None, on_feedback: "'Callable[[], None] \| None'" = None, on_docs: "'Callable[[], None] \| None'" = None)` |
| `AppSidebar` | class | `company_ui.integrations.nicegui_layout` | `(navigation: "'NavigationModel'", width: "'int'" = 264, breakpoint: "'int'" = 900, active_route: "'str \| None'" = None, on_navigate: "'Callable[[str], None] \| None'" = None, value: "'bool'" = True, owner: "'str \| None'" = None, on_support: "'Callable[[], None] \| None'" = None, on_feedback: "'Callable[[], None] \| None'" = None, on_docs: "'Callable[[], None] \| None'" = None)` |
| `ApplicationRuntime` | class | `company_ui.runtime.kernel` | `(services: "'ApplicationServices \| None'" = None, event_limit: "'int'" = 1000)` |
| `ApplicationServices` | class | `company_ui.services.bundle` | `(notifications: "'NotificationService'" = <factory>, navigation: "'NavigationService'" = <factory>, theme: "'ThemeService'" = <factory>, clipboard: "'ClipboardService'" = <factory>, downloads: "'DownloadService'" = <factory>, dialogs: "'DialogService'" = <factory>, logging: "'LoggingService'" = <factory>, errors: "'ErrorService \| None'" = None, shortcuts: "'KeyboardShortcutRegistry'" = <factory>, commands: "'CommandRegistry'" = <factory>, performance: "'PerformanceMonitor'" = <factory>, lifecycle: "'LifecycleScope'" = <factory>, preferences: "'PreferenceService \| None'" = None, workspaces: "'WorkspacePreferenceService \| None'" = None) -> 'None'` |
| `ApplicationSnapshot` | class | `company_ui.runtime.kernel` | `(state: "'StateSnapshot'", workspaces: "'tuple[WorkspaceSnapshot, ...]'") -> 'None'` |
| `AreaChart` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `AssetValidationIssue` | class | `company_ui.visual.models` | `(asset: "'str'", code: "'str'", message: "'str'") -> 'None'` |
| `AsyncAction` | class | `company_ui.async_tools.runtime` | `(timeout: "'float \| None'" = None, duplicate_policy: "'DuplicatePolicy'" = 'ignore')` |
| `AsyncContent` | class | `company_ui.integrations.nicegui_interactions` | `(state: "'AsyncState'" = 'idle', preserve_content_while_refreshing: "'bool'" = True, content: "'Callable[[], Any] \| None'" = None, on_retry: "'Callable[..., Any] \| None'" = None, empty_title: "'str'" = 'No data yet', empty_message: "'str \| None'" = None, error_title: "'str'" = 'Unable to load this content', error_message: "'str \| None'" = None, error_id: "'str \| None'" = None, skeleton_rows: "'int'" = 4)` |
| `AsyncContentSpec` | class | `company_ui.feedback.models` | `(state: "'AsyncState'" = 'idle', preserve_content_while_refreshing: "'bool'" = True, retry_label: "'str'" = 'Retry') -> 'None'` |
| `AsyncLoader` | class | `company_ui.async_tools.runtime` | `(timeout: "'float \| None'" = None, duplicate_policy: "'DuplicatePolicy'" = 'ignore')` |
| `AsyncSingleFlightCache` | class | `company_ui.performance.cache` | `(maxsize: "'int'" = 128, ttl_seconds: "'float'" = 60.0)` |
| `AsyncState` | class | `company_ui.feedback.models` | `(*values)` |
| `AuthMethod` | class | `company_ui.security.models` | `(*values)` |
| `AuthProbeConfig` | class | `company_ui.certification.live_models` | `(path: "'str'", unauthenticated_statuses: "'tuple[int, ...]'" = (302, 401, 403), authenticated_status: "'int'" = 200, required: "'bool'" = True) -> 'None'` |
| `AuthenticationAdapter` | class | `company_ui.security.models` | `(*args, **kwargs)` |
| `AuthorizationModel` | class | `company_ui.security.authorization` | `(roles: "'Mapping[str, RoleDefinition]'" = <factory>) -> 'None'` |
| `AutoRefreshController` | class | `company_ui.async_tools.runtime` | `(operation: "'Callable[[], Any \| Awaitable[Any]]'", interval_seconds: "'float'" = 60, stale_after_seconds: "'float'" = 300, run_immediately: "'bool'" = False)` |
| `Autocomplete` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", options: "'Sequence[SelectOption] \| dict[str, str]'", **kwargs)` |
| `AutocompleteSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, options: "'Sequence[SelectOption]'" = <factory>, clearable: "'bool'" = True, searchable: "'bool'" = True, min_chars: "'int'" = 1) -> 'None'` |
| `AxisSpec` | class | `company_ui.visualization.models` | `(label: "'str \| None'" = None, kind: "'AxisType'" = 'value', unit: "'str \| None'" = None, min_value: "'float \| None'" = None, max_value: "'float \| None'" = None, show_grid: "'bool'" = True, inverse: "'bool'" = False, categories: "'Sequence[Any]'" = ()) -> 'None'` |
| `AxisType` | class | `company_ui.visualization.models` | `(*values)` |
| `BREAKPOINTS` | constant | `builtins` | `` |
| `BackNavigation` | class | `company_ui.integrations.nicegui_layout` | `(label: "'str'" = 'Back', on_click: "'Callable[[], None] \| None'" = None)` |
| `BackgroundTaskIndicator` | class | `company_ui.integrations.nicegui_content` | `(label: "'str'", progress: "'float \| None'" = None, status: "'str'" = 'running', detail: "'str \| None'" = None, on_cancel: "'Callable[..., Any] \| None'" = None)` |
| `BackgroundTaskSpec` | class | `company_ui.content.models` | `(label: "'str'", progress: "'float \| None'" = None, status: "'str'" = 'running', detail: "'str \| None'" = None) -> 'None'` |
| `BadgeSpec` | class | `company_ui.components.models` | `(label: "'str'", intent: "'StatusIntent'" = 'neutral', icon: "'str \| None'" = None, subtle: "'bool'" = True) -> 'None'` |
| `Banner` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", message: "'str \| None'" = None, intent: "'FeedbackIntent'" = 'info')` |
| `BannerSpec` | class | `company_ui.feedback.models` | `(title: "'str'", message: "'str \| None'" = None, intent: "'FeedbackIntent'" = 'info', dismissible: "'bool'" = False, action_label: "'str \| None'" = None, persistent: "'bool'" = True) -> 'None'` |
| `BarChart` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `BaselineApproval` | class | `company_ui.certification.mac_baseline` | `(framework_version: "'str'", approved_at_utc: "'str'", screenshot_count: "'int'", source_report_sha256: "'str'", screenshots: "'dict[str, str]'", browsers: "'dict[str, str]'") -> 'None'` |
| `BaselineComparison` | class | `company_ui.engineering.models` | `(current: "'float \| None'", baseline: "'float \| None'", unit: "'str \| None'" = None, higher_is_better: "'bool \| None'" = None, stable_tolerance: "'float'" = 0.0) -> 'None'` |
| `BaselineComparisonView` | class | `company_ui.integrations.nicegui_engineering` | `(comparison: "'BaselineComparisonModel'", decimals: "'int'" = 3)` |
| `BeforeAfter` | class | `company_ui.integrations.nicegui_content` | `()` |
| `BoxPlot` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `Breadcrumb` | class | `company_ui.navigation.models` | `(label: "'str'", route: "'str \| None'" = None) -> 'None'` |
| `BrowserProbeConfig` | class | `company_ui.certification.live_models` | `(enabled: "'bool'" = False, required: "'bool'" = False, browsers: "'tuple[str, ...]'" = ('chrome', 'msedge'), viewports: "'tuple[tuple[str, int, int], ...]'" = (('phone-compact', 390, 844), ('phone-wide', 430, 932), ('tablet-narrow', 768, 1024), ('tablet-wide', 1024, 900), ('desktop-compact', 1280, 900), ('desktop-wide', 1440, 1000)), timeout_ms: "'int'" = 20000, screenshot_dir: "'Path \| None'" = None, storage_state: "'Path \| None'" = None) -> 'None'` |
| `BrowserScenario` | class | `company_ui.certification.mac_browser` | `(browser: "'str'", viewport: "'str'", width: "'int'", height: "'int'", theme: "'str'", density: "'str'", routes: "'tuple[str, ...]'") -> 'None'` |
| `BrowserState` | class | `company_ui.state.store` | `(initial: "'dict[str, Any] \| None'" = None, backing: "'MutableMapping[str, Any] \| None'" = None)` |
| `BulkAction` | class | `company_ui.data_table.models` | `(key: "'str'", label: "'str'", icon: "'str \| None'" = None, intent: "'str'" = 'secondary', requires_selection: "'bool'" = True, on_action: "'Callable[[Sequence[Mapping[str, Any]]], Any] \| None'" = None) -> 'None'` |
| `Button` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", intent: "'ButtonIntent'" = 'secondary', size: "'ComponentSize'" = 'medium', icon: "'str \| None'" = None, disabled: "'bool'" = False, full_width: "'bool'" = False, on_click: "'Callable[..., Any] \| None'" = None) -> "'None'"` |
| `ButtonCluster` | class | `company_ui.layouts.primitives` | `()` |
| `ButtonGroup` | class | `company_ui.integrations.nicegui_components` | `()` |
| `ButtonIntent` | class | `company_ui.components.models` | `(*values)` |
| `ButtonSpec` | class | `company_ui.components.models` | `(label: "'str'", intent: "'ButtonIntent'" = 'secondary', size: "'ComponentSize'" = 'medium', icon: "'str \| None'" = None, disabled: "'bool'" = False, loading: "'bool'" = False, full_width: "'bool'" = False, aria_label: "'str \| None'" = None) -> 'None'` |
| `CANONICAL_VIEWPORTS` | constant | `builtins` | `` |
| `CATEGORICAL` | constant | `builtins` | `` |
| `COMPATIBILITY_PATH` | constant | `pathlib._local` | `` |
| `COMPONENT_REGISTRY` | constant | `builtins` | `` |
| `CONTENT_REGISTRY` | constant | `builtins` | `` |
| `CONTROL_HEIGHTS` | constant | `builtins` | `` |
| `CONVENIENCE_REGISTRY` | constant | `builtins` | `` |
| `CancelableTask` | class | `company_ui.async_tools.runtime` | `(timeout: "'float \| None'" = None)` |
| `Card` | class | `company_ui.integrations.nicegui_components` | `(interactive: "'bool'" = False, selected: "'bool'" = False)` |
| `CertificationCheck` | class | `company_ui.certification.models` | `(key: "'str'", label: "'str'", status: "'CertificationStatus'", detail: "'str'", category: "'str'" = 'integration', required: "'bool'" = True) -> 'None'` |
| `CertificationReport` | class | `company_ui.certification.models` | `(framework_version: "'str'", checks: "'tuple[CertificationCheck, ...]'", metadata: "'Mapping[str, object]'" = <factory>) -> 'None'` |
| `CertificationStatus` | class | `company_ui.certification.models` | `(*values)` |
| `ChamberFingerprintMatrix` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", rows: "'Sequence[str]'", columns: "'Sequence[str]'", values: "'Sequence[Sequence[float]]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard')` |
| `ChartAnnotation` | class | `company_ui.visualization.models` | `(x: "'Any'", label: "'str'", y: "'float \| None'" = None, intent: "'AnnotationIntent'" = 'info', icon: "'str \| None'" = None) -> 'None'` |
| `ChartBrush` | class | `company_ui.integrations.nicegui_visualization` | `(panel: '"\'ChartPanel\'"')` |
| `ChartCrossFilter` | class | `company_ui.integrations.nicegui_visualization` | `(engine: "'CrossFilterEngine \| None'" = None)` |
| `ChartDataView` | class | `company_ui.integrations.nicegui_visualization` | `(panel: '"\'ChartPanel\'"')` |
| `ChartEvent` | class | `company_ui.visualization.models` | `(source_id: "'str'", event_type: "'str'", key: "'str \| None'" = None, value: "'Any'" = None, payload: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `ChartExport` | class | `company_ui.integrations.nicegui_visualization` | `(panel: '"\'ChartPanel\'"')` |
| `ChartFullscreen` | class | `company_ui.integrations.nicegui_visualization` | `(panel: '"\'ChartPanel\'"')` |
| `ChartKind` | class | `company_ui.visualization.models` | `(*values)` |
| `ChartLegend` | class | `company_ui.integrations.nicegui_visualization` | `(panel: '"\'ChartPanel\'"', position: "'LegendPosition \| None'" = None)` |
| `ChartPanel` | class | `company_ui.integrations.nicegui_visualization` | `(series: "'Sequence[SeriesSpec]'", spec: "'ChartPanelSpec'", thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, on_click: "'Callable[..., Any] \| None'" = None, on_select: "'Callable[..., Any] \| None'" = None, theme_mode: "'str'" = 'light')` |
| `ChartPanelSpec` | class | `company_ui.visualization.models` | `(title: "'str'", description: "'str \| None'" = None, kind: "'ChartKind'" = 'line', size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec'" = <factory>, y_axis: "'AxisSpec'" = <factory>, legend: "'LegendPosition'" = 'top', selection: "'SelectionMode'" = 'none', toolbar: "'ChartToolbarSpec'" = <factory>, empty_message: "'str'" = 'No data available', error_message: "'str'" = 'Unable to load visualization', animate: "'bool'" = True, responsive: "'bool'" = True) -> 'None'` |
| `ChartSelection` | class | `company_ui.integrations.nicegui_visualization` | `(panel: '"\'ChartPanel\'"', mode: "'SelectionMode \| None'" = None)` |
| `ChartSelectionMode` | class | `company_ui.visualization.models` | `(*values)` |
| `ChartSize` | class | `company_ui.visualization.models` | `(*values)` |
| `ChartTheme` | class | `company_ui.visualization.theme` | `(background: "'str'", text_primary: "'str'", text_secondary: "'str'", border: "'str'", grid: "'str'", surface_elevated: "'str'", accent: "'str'", success: "'str'", warning: "'str'", danger: "'str'", info: "'str'") -> 'None'` |
| `ChartToolbar` | class | `company_ui.integrations.nicegui_visualization` | `(panel: '"\'ChartPanel\'"', zoom = True, reset = True, fullscreen = True, export_image = True, export_data = True, data_view = True)` |
| `ChartToolbarSpec` | class | `company_ui.visualization.models` | `(zoom: "'bool'" = True, reset: "'bool'" = True, fullscreen: "'bool'" = True, export_image: "'bool'" = True, export_data: "'bool'" = True, data_view: "'bool'" = True) -> 'None'` |
| `ChartTooltip` | class | `company_ui.integrations.nicegui_visualization` | `(panel: '"\'ChartPanel\'"')` |
| `ChartZoom` | class | `company_ui.integrations.nicegui_visualization` | `(panel: '"\'ChartPanel\'"')` |
| `Checkbox` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", checked: "'bool'" = False, description: "'str \| None'" = None, disabled: "'bool'" = False, on_change: "'Callable[..., Any] \| None'" = None)` |
| `CheckboxGroup` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", options: "'Sequence[SelectOption]'", selected: "'Sequence[str]'" = (), disabled: "'bool'" = False, on_change: "'Callable[..., Any] \| None'" = None)` |
| `CheckboxGroupSpec` | class | `company_ui.components.models` | `(label: "'str'", options: "'Sequence[SelectOption]'", selected: "'Sequence[str]'" = <factory>, disabled: "'bool'" = False) -> 'None'` |
| `CheckboxSpec` | class | `company_ui.components.models` | `(label: "'str'", checked: "'bool'" = False, description: "'str \| None'" = None, disabled: "'bool'" = False, indeterminate: "'bool'" = False) -> 'None'` |
| `Chip` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", selected: "'bool'" = False, removable: "'bool'" = False, icon: "'str \| None'" = None, on_click: "'Callable[..., Any] \| None'" = None)` |
| `ChipSpec` | class | `company_ui.components.models` | `(label: "'str'", selected: "'bool'" = False, removable: "'bool'" = False, icon: "'str \| None'" = None) -> 'None'` |
| `ClipboardService` | class | `company_ui.services.core` | `(sink: "'Callable[[str], Any] \| None'" = None)` |
| `CodeViewer` | class | `company_ui.integrations.nicegui_content` | `(code: "'str'", language: "'str'" = 'text')` |
| `CollapsiblePanel` | class | `company_ui.integrations.nicegui_components` | `(title: "'str'", open: "'bool'" = False)` |
| `ColumnKind` | class | `company_ui.data_table.models` | `(*values)` |
| `Combobox` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", options: "'Sequence[SelectOption] \| dict[str, str]'", **kwargs)` |
| `ComboboxSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, options: "'Sequence[SelectOption]'" = <factory>, clearable: "'bool'" = True, searchable: "'bool'" = True, allow_custom: "'bool'" = True) -> 'None'` |
| `Command` | class | `company_ui.services.commands` | `(key: "'str'", label: "'str'", handler: "'Callable[[], Any]'", keywords: "'tuple[str, ...]'" = (), shortcut: "'str \| None'" = None, group: "'str'" = 'General', description: "'str \| None'" = None, enabled: "'BoolResolver'" = True, visible: "'BoolResolver'" = True) -> 'None'` |
| `CommandPalette` | class | `company_ui.integrations.nicegui_content` | `(registry: "'CommandRegistry'", placeholder: "'str'" = 'Search commands…', limit: "'int'" = 20)` |
| `CommandRegistry` | class | `company_ui.services.commands` | `(recent_limit: "'int'" = 8)` |
| `CommonalityInterpretation` | class | `company_ui.engineering.models` | `(*values)` |
| `CommonalityKind` | class | `company_ui.engineering.models` | `(*values)` |
| `CommonalityMatrix` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", rows: "'Sequence[str]'", columns: "'Sequence[str]'", scores: "'Sequence[Sequence[float]]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard')` |
| `CommonalityObservation` | class | `company_ui.engineering.models` | `(key: "'str'", label: "'str'", kind: "'CommonalityKind'", affected_exposed: "'int'", affected_total: "'int'", control_exposed: "'int'" = 0, control_total: "'int'" = 0, weight: "'float'" = 1.0, interpretation: "'CommonalityInterpretation'" = 'observed', metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `CommonalityTable` | class | `company_ui.integrations.nicegui_engineering` | `(spec: "'CommonalityTableSpec'", on_select = None)` |
| `CommonalityTableSpec` | class | `company_ui.engineering.compositions` | `(observations: "'tuple[CommonalityObservation, ...]'", title: "'str'" = 'Commonality Analysis', density: "'TableDensity'" = 'compact') -> 'None'` |
| `ComparePanel` | class | `company_ui.integrations.nicegui_content` | `()` |
| `ComparisonItem` | class | `company_ui.content.models` | `(key: "'str'", label: "'str'", left: "'Any'", right: "'Any'", delta: "'Any \| None'" = None, changed: "'bool \| None'" = None) -> 'None'` |
| `ComparisonMetric` | class | `company_ui.integrations.nicegui_content` | `(label: "'str'", current: "'Any'", baseline: "'Any'" = None, delta: "'Any'" = None, intent: "'StatusIntent'" = 'neutral', description: "'str \| None'" = None)` |
| `ComparisonMetricSpec` | class | `company_ui.content.models` | `(label: "'str'", current: "'str \| int \| float'", baseline: "'str \| int \| float \| None'" = None, delta: "'str \| int \| float \| None'" = None, intent: "'StatusIntent'" = 'neutral', description: "'str \| None'" = None) -> 'None'` |
| `ComparisonPage` | class | `company_ui.patterns.pages` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ()) -> "'None'"` |
| `CompatibilityManifest` | class | `company_ui.runtime.compatibility` | `(framework_name: "'str'" = 'company-ui', framework_version: "'str'" = '3.0.0a1', python_min: "'str'" = '3.11', python_max_exclusive: "'str'" = '3.14', nicegui_version: "'str'" = '3.15.0', primary_browsers: "'tuple[str, ...]'" = ('Microsoft Edge', 'Google Chrome'), external_cdn_required: "'bool'" = False, max_nicegui_workers_per_process: "'int'" = 1, reverse_proxy_supported: "'bool'" = True, root_path_supported: "'bool'" = True, redis_recommended_for_multi_instance: "'bool'" = True, session_affinity_required_multi_instance: "'bool'" = True, notes: "'tuple[str, ...]'" = ('NiceGUI user/browser storage requires a storage_secret.', 'Production session cookies should be HTTPS-only.', 'Multiple application instances require shared persistence for cross-instance user/general/tab state.', 'Multiple NiceGUI instances require load-balancer session affinity for page/WebSocket continuity.')) -> 'None'` |
| `ComponentCoverage` | class | `company_ui.certification.mac_coverage` | `(component: "'str'", module: "'str'", route: "'str'", coverage_kind: "'str'", via: "'str \| None'" = None, evidence: "'str \| None'" = None) -> 'None'` |
| `ComponentDefinition` | class | `company_ui.components.registry` | `(key: "'str'", category: "'str'", public_name: "'str'", purpose: "'str'", preferred_for: "'tuple[str, ...]'") -> 'None'` |
| `ComponentSize` | class | `company_ui.components.models` | `(*values)` |
| `ConcurrencyGate` | class | `company_ui.performance.runtime` | `(limit: "'int'" = 4)` |
| `ConditionalCellFormatter` | class | `company_ui.integrations.nicegui_data_table` | `()` |
| `ConditionalRule` | class | `company_ui.data_table.models` | `(operator: "'FilterOperator'", value: "'Any \| None'" = None, value2: "'Any \| None'" = None, intent: "'str'" = 'neutral') -> 'None'` |
| `ConfidenceIndicator` | class | `company_ui.integrations.nicegui_engineering` | `(spec: "'ConfidenceIndicatorSpec'")` |
| `ConfidenceIndicatorSpec` | class | `company_ui.engineering.models` | `(level: "'ConfidenceLevel'", score: "'float \| None'" = None, basis: "'str \| None'" = None, calibrated_probability: "'bool'" = False) -> 'None'` |
| `ConfidenceLevel` | class | `company_ui.engineering.models` | `(*values)` |
| `ConfirmDialog` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", description: "'str \| None'" = None, primary_label: "'str'" = 'Confirm', secondary_label: "'str'" = 'Cancel', on_confirm: "'Callable[..., Any] \| None'" = None, on_cancel: "'Callable[..., Any] \| None'" = None)` |
| `ContentColumn` | class | `company_ui.layouts.primitives` | `()` |
| `ContentDefinition` | class | `company_ui.content.registry` | `(key: "'str'", category: "'str'", public_name: "'str'", purpose: "'str'", use_when: "'tuple[str, ...]'") -> 'None'` |
| `ContentWidth` | class | `company_ui.layouts.models` | `(*values)` |
| `ContextMenu` | class | `company_ui.integrations.nicegui_interactions` | `(items: "'Sequence[MenuItemSpec]'")` |
| `ControlChart` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `ControlLimits` | class | `company_ui.engineering.models` | `(lower_control: "'float \| None'" = None, upper_control: "'float \| None'" = None, centerline: "'float \| None'" = None, unit: "'str \| None'" = None) -> 'None'` |
| `ControlState` | class | `company_ui.components.models` | `(*values)` |
| `ConvenienceDefinition` | class | `company_ui.convenience_registry` | `(key: "'str'", category: "'str'", purpose: "'str'", use_when: "'str'") -> 'None'` |
| `CorrelationIdMiddleware` | class | `company_ui.diagnostics.correlation` | `(app, header_name: "'str'" = 'x-correlation-id', trust_incoming: "'bool'" = False)` |
| `CountBadge` | class | `company_ui.integrations.nicegui_components` | `(count: "'int'", maximum: "'int'" = 999)` |
| `CountBadgeSpec` | class | `company_ui.components.models` | `(count: "'int'", maximum: "'int'" = 999) -> 'None'` |
| `CrossFilterBinding` | class | `company_ui.visualization.models` | `(source_id: "'str'", event_type: "'str'", target_key: "'str'", operator: "'str'" = 'eq') -> 'None'` |
| `CrossFilterEngine` | class | `company_ui.visualization.engine` | `(bindings: "'Sequence[CrossFilterBinding]'" = ()) -> "'None'"` |
| `CrudPage` | class | `company_ui.patterns.pages` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ()) -> "'None'"` |
| `DEFAULT_SECRET_KEYS` | constant | `builtins` | `` |
| `DENSITIES` | constant | `builtins` | `` |
| `DIVERGING` | constant | `builtins` | `` |
| `DangerConfirmDialog` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", description: "'str \| None'" = None, primary_label: "'str'" = 'Delete', secondary_label: "'str'" = 'Cancel', typed_confirmation: "'str \| None'" = None, on_confirm: "'Callable[..., Any] \| None'" = None, on_cancel: "'Callable[..., Any] \| None'" = None)` |
| `DashboardGrid` | class | `company_ui.layouts.primitives` | `()` |
| `DashboardPage` | class | `company_ui.patterns.pages` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ()) -> "'None'"` |
| `DataBinding` | class | `company_ui.data_engine.engine` | `(session: '"\'DataSession\'"', resolver: '"Callable[[\'DataSession\'], T]"')` |
| `DataEngine` | class | `company_ui.data_engine.engine` | `()` |
| `DataExplorerPage` | class | `company_ui.patterns.pages` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ()) -> "'None'"` |
| `DataLoadStatus` | class | `company_ui.performance.analytics` | `(*values)` |
| `DataQuality` | class | `company_ui.components.models` | `(*values)` |
| `DataQualityBadge` | class | `company_ui.integrations.nicegui_components` | `(quality)` |
| `DataQualityBadgeSpec` | class | `company_ui.components.models` | `(quality: "'DataQuality'") -> 'None'` |
| `DataQuery` | class | `company_ui.data_engine.models` | `(filters: "'tuple[FilterClause, ...]'" = (), search: "'str'" = '', search_fields: "'tuple[str, ...]'" = (), dimensions: "'tuple[str, ...]'" = (), metrics: "'tuple[str, ...]'" = (), sorts: "'tuple[SortClause, ...]'" = (), offset: "'int'" = 0, limit: "'int \| None'" = None) -> 'None'` |
| `DataResult` | class | `company_ui.data_engine.models` | `(rows: "'tuple[dict[str, Any], ...]'", total: "'int'", revision: "'int'" = 0, filtered_total: "'int \| None'" = None) -> 'None'` |
| `DataSession` | class | `company_ui.data_engine.engine` | `(dataset: "'Dataset'")` |
| `DataSessionSnapshot` | class | `company_ui.data_engine.models` | `(revision: "'int'", filters: "'tuple[FilterClause, ...]'", search: "'str'" = '') -> 'None'` |
| `DataTable` | class | `company_ui.integrations.nicegui_data_table` | `(rows: "'Sequence[Mapping[str, Any]] \| None'" = None, columns: "'Sequence[TableColumn] \| None'" = None, spec: "'DataTableSpec \| None'" = None, title: "'str \| None'" = None, description: "'str \| None'" = None, row_key: "'str'" = 'id', selection: "'SelectionMode'" = 'none', density: "'TableDensity'" = 'compact', expandable: "'bool'" = False, master_detail: "'bool'" = False, bulk_actions: "'Sequence[BulkAction]'" = (), row_actions: "'Sequence[RowAction]'" = (), on_select: "'Callable[..., Any] \| None'" = None, on_row_double_click: "'Callable[..., Any] \| None'" = None, on_cell_value_changed: "'Callable[..., Any] \| None'" = None, on_refresh: "'Callable[..., Any] \| None'" = None, show_toolbar: "'bool'" = True, preferences: "'PreferenceService \| None'" = None)` |
| `DataTableSpec` | class | `company_ui.data_table.models` | `(columns: "'tuple[TableColumn, ...]'", row_key: "'str'" = 'id', title: "'str \| None'" = None, description: "'str \| None'" = None, density: "'TableDensity'" = 'compact', selection: "'SelectionMode'" = 'none', pagination: "'PaginationMode'" = 'client', page_size: "'int'" = 50, page_size_options: "'tuple[int, ...]'" = (25, 50, 100, 250), searchable: "'bool'" = True, column_manager: "'bool'" = True, density_control: "'bool'" = True, export_csv: "'bool'" = True, copy_enabled: "'bool'" = True, refresh_enabled: "'bool'" = True, persist_state: "'bool'" = True, persist_key: "'str \| None'" = None, striped: "'bool'" = False, sticky_header: "'bool'" = True, expandable: "'bool'" = False, master_detail: "'bool'" = False, editable: "'bool'" = False, empty_message: "'str'" = 'No records', error_message: "'str'" = 'Unable to load records') -> 'None'` |
| `Dataset` | class | `company_ui.data_engine.engine` | `(key: "'str'", rows: "'Sequence[Mapping[str, Any]]'", dimensions: "'Sequence[Dimension]'" = (), metrics: "'Sequence[Metric]'" = (), row_key: "'str \| None'" = None)` |
| `DatePicker` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", value: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False)` |
| `DatePickerSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, precision: "'DatePrecision'" = 'date') -> 'None'` |
| `DatePrecision` | class | `company_ui.components.models` | `(*values)` |
| `DateRangePicker` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", start: "'str \| None'" = None, end: "'str \| None'" = None, description: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False)` |
| `DateRangePickerSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, start: "'str \| None'" = None, end: "'str \| None'" = None) -> 'None'` |
| `DateTimePicker` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", value: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False)` |
| `DateTimePickerSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, use_24_hour: "'bool'" = True) -> 'None'` |
| `Debouncer` | class | `company_ui.async_tools.runtime` | `(delay_seconds: "'float'")` |
| `DeltaIndicator` | class | `company_ui.integrations.nicegui_content` | `(value: "'str'", trend: "'TrendDirection'" = 'unknown', intent: "'StatusIntent'" = 'neutral')` |
| `DescriptionList` | class | `company_ui.integrations.nicegui_content` | `(items: "'Sequence[KeyValueItem]'", on_copy: "'Callable[[KeyValueItem], Any] \| None'" = None)` |
| `DesignSystem` | class | `company_ui.design.system` | `(light: "'ThemePalette'", dark: "'ThemePalette'", spacing: "'Mapping[str, int]'", radii: "'Mapping[str, int]'", control_heights: "'Mapping[str, int]'", breakpoints: "'Mapping[str, int]'", motion: "'Mapping[str, object]'", typography: "'Mapping[str, Mapping[str, object]]'", densities: "'Mapping[str, Mapping[str, int]]'") -> 'None'` |
| `DetailDrawer` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", subtitle: "'str \| None'" = None, side: "'DrawerSide'" = 'right', size: "'OverlaySize'" = 'medium', dismissible: "'bool'" = True, resizable: "'bool'" = False, persistent: "'bool'" = False)` |
| `Dialog` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", description: "'str \| None'" = None, size: "'OverlaySize'" = 'small', dismissible: "'bool'" = True, primary_label: "'str \| None'" = None, secondary_label: "'str \| None'" = 'Cancel', on_primary: "'Callable[..., Any] \| None'" = None, on_secondary: "'Callable[..., Any] \| None'" = None, close_on_primary: "'bool'" = True, close_on_secondary: "'bool'" = True, intent: "'DialogIntent'" = 'default', destructive: "'bool'" = False, typed_confirmation: "'str \| None'" = None)` |
| `DialogIntent` | class | `company_ui.overlays.models` | `(*values)` |
| `DialogRequest` | class | `company_ui.services.operations` | `(kind: "'str'", title: "'str'", message: "'str \| None'" = None, destructive: "'bool'" = False) -> 'None'` |
| `DialogService` | class | `company_ui.services.operations` | `(sink: "'Callable[[DialogRequest], Any] \| None'" = None)` |
| `DialogSpec` | class | `company_ui.overlays.models` | `(title: "'str'", description: "'str \| None'" = None, size: "'OverlaySize'" = 'small', intent: "'DialogIntent'" = 'default', dismissible: "'bool'" = True, primary_label: "'str \| None'" = None, secondary_label: "'str \| None'" = 'Cancel', destructive: "'bool'" = False, typed_confirmation: "'str \| None'" = None, close_on_primary: "'bool'" = True, close_on_secondary: "'bool'" = True) -> 'None'` |
| `DifferenceTable` | class | `company_ui.integrations.nicegui_content` | `(items: "'Sequence[ComparisonItem]'", left_label: "'str'" = 'Before', right_label: "'str'" = 'After')` |
| `Dimension` | class | `company_ui.data_engine.models` | `(key: "'str'", label: "'str \| None'" = None, field: "'str \| None'" = None) -> 'None'` |
| `DirtyStateGuard` | class | `company_ui.integrations.nicegui_interactions` | `(enabled: "'bool'" = True, message: "'str'" = 'You have unsaved changes. Leave without saving?', dirty: "'bool'" = False)` |
| `DirtyStateGuardSpec` | class | `company_ui.forms.models` | `(enabled: "'bool'" = True, message: "'str'" = 'You have unsaved changes. Leave without saving?') -> 'None'` |
| `DistributionComparisonSpec` | class | `company_ui.engineering.compositions` | `(affected_values: "'tuple[float, ...]'", control_values: "'tuple[float, ...]'", parameter: "'str'", unit: "'str \| None'" = None, affected_label: "'str'" = 'Affected', control_label: "'str'" = 'Control', spec_limits: "'LimitBand \| None'" = None) -> 'None'` |
| `DistributionPanel` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", **kwargs)` |
| `Divider` | class | `company_ui.integrations.nicegui_components` | `()` |
| `DoctorFinding` | class | `company_ui.diagnostics.doctor` | `(code: "'str'", ok: "'bool'", message: "'str'", severity: "'str'" = 'error') -> 'None'` |
| `DoctorReport` | class | `company_ui.diagnostics.doctor` | `(findings: "'tuple[DoctorFinding, ...]'") -> 'None'` |
| `DonutChart` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `DownloadRequest` | class | `company_ui.services.core` | `(filename: "'str'", content: "'bytes'", media_type: "'str'" = 'application/octet-stream') -> 'None'` |
| `DownloadService` | class | `company_ui.services.core` | `(sink: "'Callable[[DownloadRequest], Any] \| None'" = None)` |
| `DrawerSide` | class | `company_ui.overlays.models` | `(*values)` |
| `DrawerSpec` | class | `company_ui.overlays.models` | `(title: "'str'", role: "'OverlayRole'" = 'detail', side: "'DrawerSide'" = 'right', size: "'OverlaySize'" = 'medium', dismissible: "'bool'" = True, resizable: "'bool'" = False, persistent: "'bool'" = False, full_screen_on_mobile: "'bool'" = True) -> 'None'` |
| `DropdownMenu` | class | `company_ui.integrations.nicegui_interactions` | `(items: "'Sequence[MenuItemSpec]'")` |
| `DuplicatePolicy` | class | `company_ui.async_tools.models` | `(*values)` |
| `DurableJobAdapter` | class | `company_ui.jobs.runtime` | `(*args, **kwargs)` |
| `ENGINEERING_REGISTRY` | constant | `builtins` | `` |
| `EditCommitMode` | class | `company_ui.data_table.models` | `(*values)` |
| `EditableTable` | class | `company_ui.integrations.nicegui_data_table` | `(rows: "'Sequence[Mapping[str, Any]]'", columns: "'Sequence[TableColumn]'", spec: "'EditableTableSpec \| None'" = None, validate_edit: "'Callable[[Mapping[str, Any], str, Any], str \| None] \| None'" = None, save_edit: "'Callable[[Mapping[str, Any], str, Any], Any] \| None'" = None, **kwargs)` |
| `EditableTableSpec` | class | `company_ui.data_table.models` | `(columns: "'tuple[TableColumn, ...]'", row_key: "'str'" = 'id', title: "'str \| None'" = None, description: "'str \| None'" = None, density: "'TableDensity'" = 'compact', selection: "'SelectionMode'" = 'none', pagination: "'PaginationMode'" = 'client', page_size: "'int'" = 50, page_size_options: "'tuple[int, ...]'" = (25, 50, 100, 250), searchable: "'bool'" = True, column_manager: "'bool'" = True, density_control: "'bool'" = True, export_csv: "'bool'" = True, copy_enabled: "'bool'" = True, refresh_enabled: "'bool'" = True, persist_state: "'bool'" = True, persist_key: "'str \| None'" = None, striped: "'bool'" = False, sticky_header: "'bool'" = True, expandable: "'bool'" = False, master_detail: "'bool'" = False, editable: "'bool'" = True, empty_message: "'str'" = 'No records', error_message: "'str'" = 'Unable to load records', save_mode: "'str'" = 'row', commit_mode: "'EditCommitMode'" = 'optimistic', restore_focus_on_error: "'bool'" = True) -> 'None'` |
| `EmptyState` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'" = 'No data yet', message: "'str \| None'" = None, action_label: "'str \| None'" = None, compact: "'bool'" = False, on_action: "'Callable[..., Any] \| None'" = None)` |
| `EngineeringDefinition` | class | `company_ui.engineering.registry` | `(name: "'str'", category: "'str'", purpose: "'str'", when_to_use: "'str'") -> 'None'` |
| `EngineeringEntityCard` | class | `company_ui.integrations.nicegui_engineering` | `(spec: "'EngineeringEntityCardSpec'")` |
| `EngineeringEntityCardSpec` | class | `company_ui.engineering.models` | `(entity: "'EngineeringEntityRef'", title: "'str \| None'" = None, description: "'str \| None'" = None, properties: "'tuple[tuple[str, Any], ...]'" = (), show_status: "'bool'" = True, interactive: "'bool'" = False) -> 'None'` |
| `EngineeringEntityKind` | class | `company_ui.engineering.models` | `(*values)` |
| `EngineeringEntityRef` | class | `company_ui.engineering.models` | `(kind: "'EngineeringEntityKind'", identifier: "'str'", label: "'str \| None'" = None, status: "'EngineeringStatus'" = 'unknown', secondary: "'str \| None'" = None, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `EngineeringProcessTrend` | class | `company_ui.integrations.nicegui_engineering` | `(spec: "'ProcessTrendSpec'", **kwargs)` |
| `EngineeringStatus` | class | `company_ui.engineering.models` | `(*values)` |
| `EngineeringStatusBadge` | class | `company_ui.integrations.nicegui_engineering` | `(status: "'EngineeringStatus'", label: "'str \| None'" = None)` |
| `EngineeringSummarySpec` | class | `company_ui.engineering.compositions` | `(entity_card: "'EngineeringEntityCardSpec'", baseline: "'Any \| None'" = None, confidence: "'ConfidenceIndicatorSpec \| None'" = None, notes: "'tuple[str, ...]'" = ()) -> 'None'` |
| `EngineeringTimeline` | class | `company_ui.integrations.nicegui_engineering` | `(events: "'Sequence[EngineeringTimelineEvent]'")` |
| `EngineeringTimelineEvent` | class | `company_ui.engineering.models` | `(at: "'datetime'", title: "'str'", description: "'str \| None'" = None, status: "'EngineeringStatus'" = 'unknown', entity: "'EngineeringEntityRef \| None'" = None, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `EntityHeader` | class | `company_ui.integrations.nicegui_content` | `(title: "'str'", subtitle: "'str \| None'" = None, entity_type: "'str \| None'" = None, status: "'str \| None'" = None, status_intent: "'StatusIntent'" = 'neutral', icon: "'str \| None'" = None, metadata: "'Sequence[KeyValueItem]'" = ())` |
| `EntityHeaderSpec` | class | `company_ui.content.models` | `(title: "'str'", subtitle: "'str \| None'" = None, entity_type: "'str \| None'" = None, status: "'str \| None'" = None, status_intent: "'StatusIntent'" = 'neutral', icon: "'str \| None'" = None, metadata: "'Sequence[KeyValueItem]'" = <factory>) -> 'None'` |
| `Enum` | class | `enum` | `(new_class_name, names, module = None, qualname = None, type = None, start = 1, boundary = None)` |
| `EnvironmentBadge` | class | `company_ui.integrations.nicegui_layout` | `(environment: "'str'")` |
| `ErrorService` | class | `company_ui.services.operations` | `(logger: "'LoggingService \| None'" = None, prefix: "'str'" = 'UI')` |
| `ErrorState` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'" = 'Unable to load this content', message: "'str \| None'" = None, error_id: "'str \| None'" = None, compact: "'bool'" = False, on_retry: "'Callable[..., Any] \| None'" = None)` |
| `EvidenceBalance` | class | `company_ui.engineering.models` | `(support_count: "'int'", contradiction_count: "'int'", neutral_count: "'int'", weighted_balance: "'float'", support_weight: "'float'", contradiction_weight: "'float'") -> 'None'` |
| `EvidenceCard` | class | `company_ui.integrations.nicegui_engineering` | `(spec: "'EvidenceCardSpec'")` |
| `EvidenceCardSpec` | class | `company_ui.engineering.compositions` | `(evidence: "'EvidenceItem'", show_source: "'bool'" = True, show_confidence: "'bool'" = True) -> 'None'` |
| `EvidenceChannel` | class | `company_ui.engineering.models` | `(*values)` |
| `EvidenceDirection` | class | `company_ui.engineering.models` | `(*values)` |
| `EvidenceItem` | class | `company_ui.engineering.models` | `(key: "'str'", title: "'str'", channel: "'EvidenceChannel'", direction: "'EvidenceDirection'", strength: "'EvidenceStrength'" = 'moderate', summary: "'str \| None'" = None, source: "'str \| None'" = None, observed_at: "'datetime \| None'" = None, confidence: "'float \| None'" = None, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `EvidenceStrength` | class | `company_ui.engineering.models` | `(*values)` |
| `ExpandableRow` | class | `company_ui.integrations.nicegui_data_table` | `(title: "'str'" = 'Details', open: "'bool'" = False)` |
| `ExtensionDefinition` | class | `company_ui.extensions.registry` | `(key: "'str'", kind: "'ExtensionKind'", factory: "'Callable[..., Any]'", version: "'str'" = '1.0', description: "'str \| None'" = None, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `ExtensionKind` | class | `company_ui.extensions.registry` | `(*values)` |
| `ExtensionRegistry` | class | `company_ui.extensions.registry` | `() -> "'None'"` |
| `FRAMEWORK_REGISTRY_COUNTS` | constant | `builtins` | `` |
| `FRAMEWORK_VERSION` | constant | `builtins` | `` |
| `FeedbackIntent` | class | `company_ui.feedback.models` | `(*values)` |
| `FieldSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None) -> 'None'` |
| `FieldValidation` | class | `company_ui.forms.models` | `(field: "'str'", validators: "'Sequence[Validator]'" = <factory>) -> 'None'` |
| `FileUpload` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'" = 'Upload files', accept: "'Sequence[str]'" = (), multiple: "'bool'" = False, max_file_size_mb: "'int'" = 25, max_files: "'int'" = 1, disabled: "'bool'" = False, on_upload: "'Callable[..., Any] \| None'" = None)` |
| `FileUploadSpec` | class | `company_ui.components.models` | `(label: "'str'" = 'Upload files', accept: "'Sequence[str]'" = <factory>, multiple: "'bool'" = False, max_file_size_mb: "'int'" = 25, max_files: "'int'" = 1, disabled: "'bool'" = False) -> 'None'` |
| `FilterBar` | class | `company_ui.integrations.nicegui_interactions` | `(spec: "'FilterBarSpec'")` |
| `FilterBarSpec` | class | `company_ui.filters.models` | `(filters: "'Sequence[FilterDefinition]'" = <factory>, active: "'Sequence[ActiveFilter]'" = <factory>, compact_after: "'int'" = 4, show_clear_all: "'bool'" = True, show_active_count: "'bool'" = True) -> 'None'` |
| `FilterChip` | class | `company_ui.integrations.nicegui_interactions` | `(active: "'ActiveFilter'", on_remove: "'Callable[..., Any] \| None'" = None)` |
| `FilterClause` | class | `company_ui.data_engine.models` | `(field: "'str'", operation: "'FilterOperation'", value: "'Any'" = None, value2: "'Any'" = None, filter_id: "'str \| None'" = None) -> 'None'` |
| `FilterDefinition` | class | `company_ui.filters.models` | `(key: "'str'", label: "'str'", kind: "'FilterKind'", placeholder: "'str \| None'" = None, options: "'Sequence[str]'" = <factory>, default: "'object \| None'" = None, advanced: "'bool'" = False, persistence: "'FilterPersistence'" = 'session') -> 'None'` |
| `FilterDrawer` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", subtitle: "'str \| None'" = None, side: "'DrawerSide'" = 'right', size: "'OverlaySize'" = 'medium', dismissible: "'bool'" = True, resizable: "'bool'" = False, persistent: "'bool'" = False)` |
| `FilterKind` | class | `company_ui.filters.models` | `(*values)` |
| `FilterMutation` | class | `company_ui.visualization.models` | `(key: "'str'", value: "'Any'", operator: "'str'" = 'eq', source_id: "'str \| None'" = None) -> 'None'` |
| `FilterOperation` | class | `company_ui.data_engine.models` | `(*values)` |
| `FilterOperator` | class | `company_ui.data_table.models` | `(*values)` |
| `FilterPersistence` | class | `company_ui.filters.models` | `(*values)` |
| `FilterPreset` | class | `company_ui.filters.models` | `(key: "'str'", label: "'str'", values: "'Mapping[str, object]'" = <factory>, description: "'str \| None'" = None, shared: "'bool'" = False) -> 'None'` |
| `FilterPresetSelector` | class | `company_ui.integrations.nicegui_interactions` | `(presets: "'Sequence[FilterPreset]'", active_key: "'str \| None'" = None, on_select: "'Callable[..., Any] \| None'" = None)` |
| `FilterSpec` | class | `company_ui.data_table.models` | `(key: "'str'", operator: "'FilterOperator'", value: "'Any \| None'" = None, value2: "'Any \| None'" = None) -> 'None'` |
| `Form` | class | `company_ui.integrations.nicegui_interactions` | `(key: "'str'", title: "'str \| None'" = None, description: "'str \| None'" = None, dirty_guard: "'bool'" = True, validate_on: "'str'" = 'hybrid')` |
| `FormActions` | class | `company_ui.integrations.nicegui_interactions` | `(primary_label: "'str'" = 'Save', secondary_label: "'str'" = 'Cancel', destructive_label: "'str \| None'" = None, sticky: "'bool'" = False, align: "'str'" = 'end', on_primary: "'Callable[..., Any] \| None'" = None, on_secondary: "'Callable[..., Any] \| None'" = None, on_destructive: "'Callable[..., Any] \| None'" = None, form: "'Form \| None'" = None)` |
| `FormActionsSpec` | class | `company_ui.forms.models` | `(primary_label: "'str'" = 'Save', secondary_label: "'str'" = 'Cancel', destructive_label: "'str \| None'" = None, sticky: "'bool'" = False, align: "'str'" = 'end') -> 'None'` |
| `FormDialog` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", description: "'str \| None'" = None, size: "'OverlaySize'" = 'small', dismissible: "'bool'" = True, primary_label: "'str \| None'" = None, secondary_label: "'str \| None'" = 'Cancel', on_primary: "'Callable[..., Any] \| None'" = None, on_secondary: "'Callable[..., Any] \| None'" = None, close_on_primary: "'bool'" = True, close_on_secondary: "'bool'" = True, intent: "'DialogIntent'" = 'default', destructive: "'bool'" = False, typed_confirmation: "'str \| None'" = None)` |
| `FormDrawer` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", subtitle: "'str \| None'" = None, side: "'DrawerSide'" = 'right', size: "'OverlaySize'" = 'medium', dismissible: "'bool'" = True, resizable: "'bool'" = False, persistent: "'bool'" = False)` |
| `FormField` | class | `company_ui.integrations.nicegui_interactions` | `(key: "'str'", label: "'str'", description: "'str \| None'" = None, required: "'bool'" = False, error: "'str \| None'" = None, full_width: "'bool'" = False)` |
| `FormFieldSpec` | class | `company_ui.forms.models` | `(key: "'str'", label: "'str'", description: "'str \| None'" = None, required: "'bool'" = False, error: "'str \| None'" = None, full_width: "'bool'" = False) -> 'None'` |
| `FormSection` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", description: "'str \| None'" = None, collapsible: "'bool'" = False, default_open: "'bool'" = True)` |
| `FormSectionSpec` | class | `company_ui.forms.models` | `(title: "'str'", description: "'str \| None'" = None, collapsible: "'bool'" = False, default_open: "'bool'" = True) -> 'None'` |
| `FormSpec` | class | `company_ui.forms.models` | `(key: "'str'", title: "'str \| None'" = None, description: "'str \| None'" = None, submit_label: "'str'" = 'Save', cancel_label: "'str'" = 'Cancel', dirty_guard: "'bool'" = True, validate_on: "'str'" = 'hybrid') -> 'None'` |
| `FormStack` | class | `company_ui.layouts.primitives` | `()` |
| `FormState` | class | `company_ui.forms.models` | `(values: "'Mapping[str, object \| None]'" = <factory>, initial_values: "'Mapping[str, object \| None]'" = <factory>, issues: "'Sequence[ValidationIssue]'" = <factory>, submitting: "'bool'" = False, submitted: "'bool'" = False) -> 'None'` |
| `FreshnessIndicator` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", stale: "'bool'" = False)` |
| `FreshnessIndicatorSpec` | class | `company_ui.components.models` | `(label: "'str'", stale: "'bool'" = False) -> 'None'` |
| `FullScreenDialog` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", **kwargs)` |
| `FullScreenWorkspace` | class | `company_ui.layouts.primitives` | `()` |
| `GRID_COLUMNS` | constant | `builtins` | `` |
| `Gap` | class | `company_ui.layouts.models` | `(*values)` |
| `Gauge` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `GoldCertificationReport` | class | `company_ui.certification.live_models` | `(framework_version: "'str'", target_url: "'str'", checks: "'tuple[LiveGateResult, ...]'", metadata: "'Mapping[str, object]'" = <factory>) -> 'None'` |
| `GovernanceFinding` | class | `company_ui.governance.models` | `(rule: "'str'", path: "'str'", detail: "'str'", line: "'int \| None'" = None, severity: "'str'" = 'error') -> 'None'` |
| `GovernanceReport` | class | `company_ui.governance.models` | `(root: "'Path'", findings: "'tuple[GovernanceFinding, ...]'" = <factory>) -> 'None'` |
| `Grid` | class | `company_ui.layouts.primitives` | `(preset: "'GridPreset'" = 'auto')` |
| `GridPlacement` | class | `company_ui.workspace.models` | `(panel_id: "'str'", breakpoint: "'WorkspaceBreakpoint'", column: "'int'", row: "'int'", column_span: "'int'", row_span: "'int'") -> 'None'` |
| `GridPreset` | class | `company_ui.layouts.models` | `(*values)` |
| `HeaderAuthenticationAdapter` | class | `company_ui.security.models` | `(config: "'HeaderIdentityConfig \| None'" = None, trusted_proxies: "'TrustedProxyPolicy \| None'" = None, assertion_secret: "'str \| None'" = None)` |
| `HeaderIdentityConfig` | class | `company_ui.security.models` | `(subject_header: "'str'" = 'x-auth-user', display_name_header: "'str'" = 'x-auth-name', email_header: "'str'" = 'x-auth-email', roles_header: "'str'" = 'x-auth-roles', permissions_header: "'str'" = 'x-auth-permissions', separator: "'str'" = ',', require_trusted_proxy: "'bool'" = True, assertion_header: "'str'" = 'x-company-auth-assertion') -> 'None'` |
| `HealthCheck` | class | `company_ui.diagnostics.health` | `(name: "'str'", check: "'CheckCallable'", critical: "'bool'" = True, timeout_seconds: "'float'" = 3.0) -> 'None'` |
| `HealthRegistry` | class | `company_ui.diagnostics.health` | `()` |
| `HealthReport` | class | `company_ui.diagnostics.health` | `(state: "'HealthState'", checks: "'tuple[HealthResult, ...]'", generated_at: "'datetime'") -> 'None'` |
| `HealthResult` | class | `company_ui.diagnostics.health` | `(name: "'str'", state: "'HealthState'", detail: "'str'" = '', duration_ms: "'float'" = 0.0, critical: "'bool'" = True, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `HealthState` | class | `company_ui.diagnostics.health` | `(*values)` |
| `Heatmap` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `Histogram` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `HypothesisStatus` | class | `company_ui.engineering.models` | `(*values)` |
| `ICON_ALIASES` | constant | `builtins` | `` |
| `ICON_REGISTRY` | constant | `builtins` | `` |
| `ICON_SIZE_PX` | constant | `builtins` | `` |
| `ILLUSTRATION_REGISTRY` | constant | `builtins` | `` |
| `INTERACTION_REGISTRY` | constant | `builtins` | `` |
| `IconButton` | class | `company_ui.integrations.nicegui_components` | `(icon: "'str'", label: "'str'", intent: "'ButtonIntent'" = 'ghost', size: "'ComponentSize'" = 'medium', disabled: "'bool'" = False, selected: "'bool'" = False, on_click: "'Callable[..., Any] \| None'" = None) -> "'None'"` |
| `IconButtonSpec` | class | `company_ui.components.models` | `(icon: "'str'", label: "'str'", intent: "'ButtonIntent'" = 'ghost', size: "'ComponentSize'" = 'medium', disabled: "'bool'" = False, selected: "'bool'" = False) -> 'None'` |
| `IconCategory` | class | `company_ui.visual.models` | `(*values)` |
| `IconDefinition` | class | `company_ui.visual.models` | `(key: "'str'", category: "'str'", domain: "'str'", path: "'str'", aliases: "'tuple[str, ...]'" = (), theme: "'str'" = 'currentColor', source: "'str'" = 'company-ui-project-authored', license: "'str'" = 'Company UI project-authored asset') -> 'None'` |
| `IconSize` | class | `company_ui.visual.models` | `(*values)` |
| `Icons` | class | `company_ui.visual.keys` | `(*values)` |
| `IdentityMiddleware` | class | `company_ui.security.models` | `(app, adapter: "'AuthenticationAdapter'")` |
| `IllustrationDefinition` | class | `company_ui.visual.models` | `(key: "'str'", path: "'str'", category: "'str'" = 'state', theme: "'str'" = 'currentColor') -> 'None'` |
| `Illustrations` | class | `company_ui.visual.keys` | `(*values)` |
| `ImageViewer` | class | `company_ui.integrations.nicegui_content` | `(source: "'str'", allow_remote: "'bool'" = False, alt: "'str'" = 'Image', caption: "'str \| None'" = None)` |
| `InProcessJobAdapter` | class | `company_ui.jobs.runtime` | `(max_jobs: "'int'" = 256)` |
| `InputWidth` | class | `company_ui.components.models` | `(*values)` |
| `InspectorDrawer` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", subtitle: "'str \| None'" = None, side: "'DrawerSide'" = 'right', size: "'OverlaySize'" = 'medium', dismissible: "'bool'" = True, resizable: "'bool'" = False, persistent: "'bool'" = False)` |
| `InteractionDefinition` | class | `company_ui.interaction_registry` | `(key: "'str'", category: "'str'", public_name: "'str'", purpose: "'str'", use_when: "'tuple[str, ...]'", avoid_when: "'tuple[str, ...]'" = ()) -> 'None'` |
| `InteractiveCard` | class | `company_ui.integrations.nicegui_components` | `(selected: "'bool'" = False, on_click: "'Callable[..., Any] \| None'" = None)` |
| `InvestigationContextBar` | class | `company_ui.integrations.nicegui_engineering` | `(spec: "'InvestigationContextSpec'")` |
| `InvestigationContextSpec` | class | `company_ui.engineering.models` | `(investigation_id: "'str'", hypothesis: "'str'", owner: "'str'", stage: "'str'", updated: "'str'") -> 'None'` |
| `JOB_REGISTRY` | constant | `builtins` | `` |
| `JobCallable` | constant | `collections.abc` | `` |
| `JobDefinition` | class | `company_ui.jobs.registry` | `(key: 'str', public_name: 'str', purpose: 'str', use_when: 'tuple[str, ...]', avoid_when: 'str') -> 'None'` |
| `JobHandle` | class | `company_ui.jobs.models` | `(job_id: "'str'", label: "'str \| None'" = None, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `JobSnapshot` | class | `company_ui.jobs.models` | `(handle: "'JobHandle'", status: "'JobStatus'", progress: "'float \| None'" = None, message: "'str \| None'" = None, error: "'str \| None'" = None, result_available: "'bool'" = False) -> 'None'` |
| `JobStatus` | class | `company_ui.jobs.models` | `(*values)` |
| `JsonLogFormatter` | class | `company_ui.diagnostics.logging` | `(fmt = None, datefmt = None, style = '%', validate = True, defaults = None)` |
| `JsonViewer` | class | `company_ui.integrations.nicegui_content` | `(value: "'Any'", read_only: "'bool'" = True)` |
| `KeyValueItem` | class | `company_ui.content.models` | `(key: "'str'", label: "'str'", value: "'Any'", description: "'str \| None'" = None, copyable: "'bool'" = False, intent: "'StatusIntent'" = 'neutral') -> 'None'` |
| `KeyValueList` | class | `company_ui.integrations.nicegui_content` | `(items: "'Sequence[KeyValueItem]'", on_copy: "'Callable[[KeyValueItem], Any] \| None'" = None)` |
| `KeyboardShortcut` | class | `company_ui.services.keyboard` | `(keys: "'str'", handler: "'Callable[[], Any]'", description: "'str'", scope: "'str'" = 'page', allow_in_input: "'bool'" = False) -> 'None'` |
| `KeyboardShortcutRegistry` | class | `company_ui.services.keyboard` | `()` |
| `LAB_PORT` | constant | `builtins` | `` |
| `LAB_TITLE` | constant | `builtins` | `` |
| `LAB_VERSION` | constant | `builtins` | `` |
| `LayoutSlot` | class | `company_ui.layouts.models` | `(*values)` |
| `LazyResource` | class | `company_ui.performance.runtime` | `(loader: "'Callable[[], T \| Awaitable[T]]'", disposer: "'Callable[[T], Any \| Awaitable[Any]] \| None'" = None)` |
| `LegendPosition` | class | `company_ui.visualization.models` | `(*values)` |
| `LifecycleScope` | class | `company_ui.performance.runtime` | `() -> "'None'"` |
| `LimitBand` | class | `company_ui.engineering.models` | `(lower_spec: "'float \| None'" = None, upper_spec: "'float \| None'" = None, target: "'float \| None'" = None, lower_warning: "'float \| None'" = None, upper_warning: "'float \| None'" = None, unit: "'str \| None'" = None) -> 'None'` |
| `LineChart` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `LineStyle` | class | `company_ui.visualization.models` | `(*values)` |
| `LinkedAnalysisController` | class | `company_ui.visualization.engine` | `(engine: "'CrossFilterEngine \| None'" = None) -> "'None'"` |
| `LiveCertificationConfig` | class | `company_ui.certification.live_models` | `(target_url: "'str'", health_path: "'str'" = '/healthz', readiness_path: "'str'" = '/readyz', websocket_path: "'str'" = '/_nicegui_ws/socket.io/?EIO=4&transport=websocket', timeout_seconds: "'float'" = 10.0, expected_status: "'int'" = 200, require_security_headers: "'bool'" = True, expected_security_headers: "'tuple[str, ...]'" = ('x-content-type-options', 'referrer-policy'), headers: "'Mapping[str, str]'" = <factory>, browser: "'BrowserProbeConfig'" = <factory>, auth: "'AuthProbeConfig \| None'" = None, load: "'LoadProbeConfig \| None'" = None, evidence_path: "'Path \| None'" = None, require_offline_certification: "'bool'" = True, require_nicegui_runtime: "'bool'" = True) -> 'None'` |
| `LiveGateResult` | class | `company_ui.certification.live_models` | `(key: "'str'", label: "'str'", status: "'LiveGateStatus'", detail: "'str'", category: "'str'", required: "'bool'" = True, duration_ms: "'float \| None'" = None, evidence: "'Mapping[str, object]'" = <factory>) -> 'None'` |
| `LiveGateStatus` | class | `company_ui.certification.live_models` | `(*values)` |
| `LoadProbeConfig` | class | `company_ui.certification.live_models` | `(url: "'str'", requests: "'int'" = 100, concurrency: "'int'" = 10, timeout_seconds: "'float'" = 10.0, min_success_rate: "'float'" = 0.99, max_p95_ms: "'float \| None'" = None) -> 'None'` |
| `LogViewer` | class | `company_ui.integrations.nicegui_content` | `(lines: "'Sequence[str]'" = (), max_lines: "'int'" = 500)` |
| `LoggingService` | class | `company_ui.services.operations` | `(logger: "'logging.Logger \| None'" = None)` |
| `MOTION` | constant | `builtins` | `` |
| `MacBrowserReport` | class | `company_ui.certification.mac_browser` | `(results: "'tuple[RouteBrowserResult, ...]'", browsers: "'dict[str, str]'", baseline_dir: "'str \| None'") -> 'None'` |
| `MacCertificationReport` | class | `company_ui.certification.mac_certify` | `(framework_version: "'str'", nicegui_version: "'str'", generated_at_utc: "'str'", target_url: "'str'", exhaustive: "'bool'", require_baseline: "'bool'", baseline_verified: "'bool'", baseline_detail: "'str'", preflight: "'tuple[PreflightCheck, ...]'", live: "'dict[str, object]'", browser: "'dict[str, object]'", coverage: "'dict[str, object]'", lab_log: "'str'") -> 'None'` |
| `Mapping` | constant | `typing` | `` |
| `MarkdownViewer` | class | `company_ui.integrations.nicegui_content` | `(content: "'str'", extras: "'Sequence[str] \| None'" = None)` |
| `MarkerShape` | class | `company_ui.visualization.models` | `(*values)` |
| `MasterDetailLayout` | class | `company_ui.layouts.primitives` | `()` |
| `MasterDetailPage` | class | `company_ui.patterns.pages` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ()) -> "'None'"` |
| `MasterDetailTable` | class | `company_ui.integrations.nicegui_data_table` | `(rows, columns, detail_renderer: "'Callable[[Mapping[str, Any]], Any]'", detail_title: "'Callable[[Mapping[str, Any]], str] \| None'" = None, **kwargs)` |
| `MeasurementPoint` | class | `company_ui.engineering.models` | `(x: "'Any'", value: "'float'", entity_key: "'str \| None'" = None, status: "'EngineeringStatus'" = 'normal', metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `MenuItemSpec` | class | `company_ui.overlays.models` | `(key: "'str'", label: "'str'", icon: "'str \| None'" = None, disabled: "'bool'" = False, danger: "'bool'" = False, shortcut: "'str \| None'" = None, separator_before: "'bool'" = False, on_select: "'MenuCallback \| None'" = None, close_on_select: "'bool'" = True) -> 'None'` |
| `MenuSpec` | class | `company_ui.overlays.models` | `(items: "'Sequence[MenuItemSpec]'" = <factory>, searchable: "'bool'" = False, max_height: "'int \| None'" = 360) -> 'None'` |
| `Metric` | class | `company_ui.data_engine.models` | `(key: "'str'", label: "'str \| None'" = None, field: "'str \| None'" = None, aggregation: "'Aggregation'" = 'sum') -> 'None'` |
| `MetricCard` | class | `company_ui.integrations.nicegui_content` | `(label: "'str'", value: "'Any'", description: "'str \| None'" = None, delta: "'str \| None'" = None, trend: "'TrendDirection'" = 'unknown', intent: "'StatusIntent'" = 'neutral', icon: "'str \| None'" = None, help_text: "'str \| None'" = None, on_click: "'Callable[..., Any] \| None'" = None)` |
| `MetricCardSpec` | class | `company_ui.content.models` | `(label: "'str'", value: "'str \| int \| float'", description: "'str \| None'" = None, delta: "'str \| None'" = None, trend: "'TrendDirection'" = 'unknown', intent: "'StatusIntent'" = 'neutral', icon: "'str \| None'" = None, clickable: "'bool'" = False, help_text: "'str \| None'" = None) -> 'None'` |
| `MetricStrip` | class | `company_ui.integrations.nicegui_content` | `()` |
| `MobileNavigationDrawer` | class | `company_ui.integrations.nicegui_layout` | `(navigation: "'NavigationModel'", active_route: "'str \| None'" = None, on_navigate: "'Callable[[str], None] \| None'" = None, value: "'bool'" = False, owner: "'str \| None'" = None, on_support: "'Callable[[], None] \| None'" = None, on_feedback: "'Callable[[], None] \| None'" = None, on_docs: "'Callable[[], None] \| None'" = None)` |
| `MonitoringPage` | class | `company_ui.patterns.pages` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ()) -> "'None'"` |
| `MultiSelect` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", options: "'Sequence[SelectOption] \| dict[str, str]'", value: "'Sequence[str]'" = (), **kwargs)` |
| `MultiSelectSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, options: "'Sequence[SelectOption]'" = <factory>, clearable: "'bool'" = True, searchable: "'bool'" = False, max_selected: "'int \| None'" = None) -> 'None'` |
| `NICEGUI_VERSION` | constant | `builtins` | `` |
| `NavItem` | class | `company_ui.navigation.models` | `(id: "'str'", label: "'str'", route: "'str \| None'" = None, icon: "'str \| None'" = None, badge: "'str \| int \| None'" = None, permission: "'str \| None'" = None, children: '"tuple[\'NavItem\', ...]"' = <factory>) -> 'None'` |
| `NavSection` | class | `company_ui.navigation.models` | `(id: "'str'", label: "'str \| None'", items: "'tuple[NavItem, ...]'") -> 'None'` |
| `NavigationModel` | class | `company_ui.navigation.models` | `(sections: "'tuple[NavSection, ...]'") -> 'None'` |
| `NavigationService` | class | `company_ui.services.core` | `(sink: "'Callable[[NavigationTarget], Any] \| None'" = None, history_limit: "'int'" = 100)` |
| `NavigationTarget` | class | `company_ui.services.core` | `(path: "'str'", query: "'dict[str, Any] \| None'" = None, replace: "'bool'" = False) -> 'None'` |
| `NiceGUIRuntimeAdapter` | class | `company_ui.integrations.nicegui_runtime` | `(config: "'RuntimeConfig'", health: "'HealthRegistry \| None'" = None, auth_adapter: "'AuthenticationAdapter \| None'" = None, authorization: "'AuthorizationModel \| None'" = None, security_headers: "'SecurityHeaders \| None'" = None)` |
| `NiceGUIStateServices` | class | `company_ui.integrations.nicegui_state` | `()` |
| `NiceGUIThemeAdapter` | class | `company_ui.integrations.nicegui_theme` | `(default_mode: "'ThemeMode'" = 'system', default_density: "'str'" = 'compact', storage_key: "'str'" = 'company_ui_theme') -> 'None'` |
| `NoResultsState` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'" = 'No matching results', message: "'str \| None'" = None, action_label: "'str \| None'" = 'Clear filters', compact: "'bool'" = False, on_clear: "'Callable[..., Any] \| None'" = None)` |
| `NotFoundState` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'" = 'Page not found', message: "'str \| None'" = None, compact: "'bool'" = False, on_back: "'Callable[..., Any] \| None'" = None)` |
| `NotificationCenter` | class | `company_ui.integrations.nicegui_content` | `(notifications: "'Sequence[Any]'" = (), empty_message: "'str'" = 'No notifications')` |
| `NotificationService` | class | `company_ui.services.core` | `(sink: "'Callable[[ToastSpec], Any] \| None'" = None, history_limit: "'int'" = 100)` |
| `NumberInput` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", value: "'float \| None'" = None, minimum: "'float \| None'" = None, maximum: "'float \| None'" = None, step: "'float \| None'" = None, unit: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, on_change: "'Callable[..., Any] \| None'" = None)` |
| `NumberInputSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, minimum: "'float \| None'" = None, maximum: "'float \| None'" = None, step: "'float \| None'" = None, unit: "'str \| None'" = None) -> 'None'` |
| `OfflineState` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'" = 'Connection unavailable', message: "'str \| None'" = None, compact: "'bool'" = False, on_retry: "'Callable[..., Any] \| None'" = None)` |
| `OutOfSpecIndicator` | class | `company_ui.integrations.nicegui_engineering` | `(value: "'float \| None'" = None, limits: "'LimitBand \| None'" = None, evaluation: "'SpecEvaluation \| None'" = None, decimals: "'int'" = 3)` |
| `OverlayLayer` | class | `company_ui.overlays.models` | `(*values)` |
| `OverlayRole` | class | `company_ui.overlays.models` | `(*values)` |
| `OverlaySize` | class | `company_ui.overlays.models` | `(*values)` |
| `PATTERN_REGISTRY` | constant | `builtins` | `` |
| `PERFORMANCE_REGISTRY` | constant | `builtins` | `` |
| `Page` | class | `company_ui.layouts.primitives` | `(width: "'ContentWidth'" = 'wide')` |
| `PageHeader` | class | `company_ui.integrations.nicegui_layout` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ())` |
| `PageNavigation` | class | `company_ui.integrations.nicegui_layout` | `(previous: "'tuple[str, Callable[[], None]] \| None'" = None, next: "'tuple[str, Callable[[], None]] \| None'" = None)` |
| `PagePattern` | class | `company_ui.patterns.registry` | `(*values)` |
| `PageState` | class | `company_ui.state.models` | `(status: "'PageStatus'" = 'idle', message: "'str \| None'" = None, error_id: "'str \| None'" = None, last_updated: "'datetime \| None'" = None, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `PageStatus` | class | `company_ui.state.models` | `(*values)` |
| `PaginationMode` | class | `company_ui.data_table.models` | `(*values)` |
| `Panel` | class | `company_ui.integrations.nicegui_components` | `(interactive: "'bool'" = False, selected: "'bool'" = False)` |
| `PanelSize` | class | `company_ui.layouts.models` | `(*values)` |
| `PanelSpec` | class | `company_ui.workspace.models` | `(panel_id: "'str'", preferred_columns: "'int'" = 6, preferred_rows: "'int'" = 4, min_columns: "'int'" = 2, max_columns: "'int \| None'" = None, min_rows: "'int'" = 2, max_rows: "'int \| None'" = None, phone_full_width: "'bool'" = True, locked: "'bool'" = False, metadata: "'Mapping[str, object]'" = <factory>) -> 'None'` |
| `ParetoChart` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", categories: "'Sequence[str]'", values: "'Sequence[float]'", cumulative_pct: "'Sequence[float]'", description: "'str \| None'" = None, **kwargs)` |
| `PasswordInput` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'" = 'Password', **kwargs)` |
| `PatternDefinition` | class | `company_ui.patterns.registry` | `(pattern: "'PagePattern'", purpose: "'str'", required_slots: "'tuple[LayoutSlot, ...]'", optional_slots: "'tuple[LayoutSlot, ...]'", slot_order: "'tuple[LayoutSlot, ...]'", content_width: "'ContentWidth'", primary_grid: "'GridPreset \| None'", desktop_behavior: "'str'", tablet_behavior: "'str'", phone_behavior: "'str'") -> 'None'` |
| `PatternPage` | class | `company_ui.patterns.pages` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ()) -> "'None'"` |
| `PatternSurface` | class | `company_ui.patterns.pages` | `(*values)` |
| `PerformanceBudget` | class | `company_ui.performance.runtime` | `(name: "'str'", warning_ms: "'float'", critical_ms: "'float \| None'" = None) -> 'None'` |
| `PerformanceDefinition` | class | `company_ui.performance.registry` | `(key: 'str', purpose: 'str', use_when: 'str', avoid_when: 'str') -> 'None'` |
| `PerformanceMonitor` | class | `company_ui.performance.runtime` | `(max_samples: "'int'" = 500)` |
| `PerformanceSample` | class | `company_ui.performance.runtime` | `(name: "'str'", duration_ms: "'float'", metadata: "'dict[str, Any]'") -> 'None'` |
| `PermissionDeniedState` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'" = 'Access restricted', message: "'str \| None'" = None, compact: "'bool'" = False)` |
| `PinPosition` | class | `company_ui.data_table.models` | `(*values)` |
| `PlotlyPanel` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", figure: "'Any'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard')` |
| `Popover` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str \| None'" = None)` |
| `PopoverSpec` | class | `company_ui.overlays.models` | `(title: "'str \| None'" = None, dismissible: "'bool'" = True, placement: "'str'" = 'bottom-start') -> 'None'` |
| `PopulationComparison` | class | `company_ui.engineering.models` | `(affected: "'PopulationSummary'", control: "'PopulationSummary'", mean_delta: "'float \| None'", mean_ratio: "'float \| None'", standardized_mean_difference: "'float \| None'") -> 'None'` |
| `PopulationComparisonPanel` | class | `company_ui.integrations.nicegui_engineering` | `(spec: "'DistributionComparisonSpec'", **kwargs)` |
| `PopulationRole` | class | `company_ui.engineering.models` | `(*values)` |
| `PopulationSummary` | class | `company_ui.engineering.models` | `(name: "'str'", role: "'PopulationRole'", count: "'int'", mean: "'float \| None'", median: "'float \| None'", stdev: "'float \| None'", minimum: "'float \| None'", maximum: "'float \| None'", p10: "'float \| None'", p90: "'float \| None'", unit: "'str \| None'" = None) -> 'None'` |
| `PreferenceService` | class | `company_ui.services.preferences` | `(backing: "'MutableMapping[str, Any]'", key: "'str'" = 'company_ui_preferences')` |
| `PreflightCheck` | class | `company_ui.certification.mac_preflight` | `(key: "'str'", status: "'str'", detail: "'str'", required: "'bool'" = True) -> 'None'` |
| `PreviewDialog` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", description: "'str \| None'" = None, size: "'OverlaySize'" = 'small', dismissible: "'bool'" = True, primary_label: "'str \| None'" = None, secondary_label: "'str \| None'" = 'Cancel', on_primary: "'Callable[..., Any] \| None'" = None, on_secondary: "'Callable[..., Any] \| None'" = None, close_on_primary: "'bool'" = True, close_on_secondary: "'bool'" = True, intent: "'DialogIntent'" = 'default', destructive: "'bool'" = False, typed_confirmation: "'str \| None'" = None)` |
| `Principal` | class | `company_ui.security.models` | `(subject: "'str'", display_name: "'str \| None'" = None, email: "'str \| None'" = None, roles: "'frozenset[str]'" = frozenset({}), permissions: "'frozenset[str]'" = frozenset({}), authenticated: "'bool'" = True, method: "'AuthMethod'" = 'custom', metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `ProcessTrendPanel` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `ProcessTrendSpec` | class | `company_ui.engineering.compositions` | `(parameter: "'str'", points: "'tuple[MeasurementPoint, ...]'", unit: "'str \| None'" = None, spec_limits: "'LimitBand \| None'" = None, control_limits: "'ControlLimits \| None'" = None, title: "'str \| None'" = None, description: "'str \| None'" = None) -> 'None'` |
| `ProgressBar` | class | `company_ui.integrations.nicegui_interactions` | `(value: "'float \| None'" = None, indeterminate: "'bool'" = False, label: "'str \| None'" = None)` |
| `ProgressMetric` | class | `company_ui.integrations.nicegui_content` | `(label: "'str'", value: "'float'", target: "'float'" = 1.0, display_value: "'str \| None'" = None, description: "'str \| None'" = None)` |
| `ProgressSnapshot` | class | `company_ui.async_tools.runtime` | `(value: "'float'" = 0.0, label: "'str \| None'" = None) -> 'None'` |
| `ProgressSpec` | class | `company_ui.feedback.models` | `(value: "'float \| None'" = None, label: "'str \| None'" = None, indeterminate: "'bool'" = False) -> 'None'` |
| `ProgressSteps` | class | `company_ui.integrations.nicegui_content` | `(steps: "'Sequence[StepSpec]'")` |
| `ProgressTask` | class | `company_ui.async_tools.runtime` | `(timeout: "'float \| None'" = None)` |
| `PropertyGrid` | class | `company_ui.integrations.nicegui_content` | `(items: "'Sequence[KeyValueItem]'")` |
| `ProxyConfig` | class | `company_ui.runtime.config` | `(enabled: "'bool'" = False, trusted_proxies: "'tuple[str, ...]'" = ('127.0.0.1', '::1'), root_path: "'str'" = '') -> 'None'` |
| `RADII` | constant | `builtins` | `` |
| `RELEASE_STATUS` | constant | `builtins` | `` |
| `ROUTES` | constant | `builtins` | `` |
| `RUNTIME_REGISTRY` | constant | `builtins` | `` |
| `RadialProfilePlot` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", affected: "'Sequence[float]'", control: "'Sequence[float]'", unit: "'str'" = '', description: "'str \| None'" = None, size: "'ChartSize'" = 'standard')` |
| `RadioGroup` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", options: "'Sequence[SelectOption]'", selected: "'str \| None'" = None, on_change: "'Callable[..., Any] \| None'" = None)` |
| `RadioGroupSpec` | class | `company_ui.components.models` | `(label: "'str'", options: "'Sequence[SelectOption]'", selected: "'str \| None'" = None, disabled: "'bool'" = False) -> 'None'` |
| `RangeSlider` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", low: "'float'", high: "'float'", minimum: "'float'" = 0, maximum: "'float'" = 100, step: "'float'" = 1, unit: "'str \| None'" = None, disabled: "'bool'" = False, on_change: "'Callable[..., Any] \| None'" = None)` |
| `RangeSliderSpec` | class | `company_ui.components.models` | `(label: "'str'", low: "'float'", high: "'float'", minimum: "'float'" = 0, maximum: "'float'" = 100, step: "'float'" = 1, unit: "'str \| None'" = None, disabled: "'bool'" = False) -> 'None'` |
| `RcaEvidencePanel` | class | `company_ui.integrations.nicegui_engineering` | `(spec: "'RcaEvidencePanelSpec'")` |
| `RcaEvidencePanelSpec` | class | `company_ui.engineering.compositions` | `(hypothesis: "'RcaHypothesis'", title: "'str'" = 'Root Cause Evidence', show_contradictions: "'bool'" = True, group_by_channel: "'bool'" = True) -> 'None'` |
| `RcaHypothesis` | class | `company_ui.engineering.models` | `(key: "'str'", title: "'str'", description: "'str \| None'" = None, status: "'HypothesisStatus'" = 'new', evidence: "'tuple[EvidenceItem, ...]'" = (), commonalities: "'tuple[CommonalityObservation, ...]'" = (), confidence: "'ConfidenceIndicatorSpec \| None'" = None, explicit_rank_score: "'float \| None'" = None, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `RcaWorkspaceSpec` | class | `company_ui.engineering.compositions` | `(hypotheses: "'tuple[RcaHypothesis, ...]'", selected_key: "'str \| None'" = None, candidate_limit: "'int'" = 10) -> 'None'` |
| `RefreshStatus` | class | `company_ui.async_tools.models` | `(last_attempt: "'datetime \| None'" = None, last_success: "'datetime \| None'" = None, last_error: "'str \| None'" = None, refreshing: "'bool'" = False, stale_after_seconds: "'float'" = 300.0) -> 'None'` |
| `ResizablePanel` | class | `company_ui.layouts.primitives` | `()` |
| `ResponsiveDrawer` | class | `company_ui.integrations.nicegui_interactions` | `(title: "'str'", subtitle: "'str \| None'" = None, side: "'DrawerSide'" = 'right', size: "'OverlaySize'" = 'medium', dismissible: "'bool'" = True, resizable: "'bool'" = False, persistent: "'bool'" = False)` |
| `ResponsiveGrid` | class | `company_ui.layouts.primitives` | `(preset: "'GridPreset'" = 'auto')` |
| `ResponsiveRule` | class | `company_ui.layouts.models` | `(phone: "'str'", tablet: "'str'", laptop: "'str'", desktop: "'str'") -> 'None'` |
| `RetryPolicy` | class | `company_ui.performance.runtime` | `(attempts: "'int'" = 3, base_delay_seconds: "'float'" = 0.25, max_delay_seconds: "'float'" = 2.0, jitter: "'float'" = 0.1) -> 'None'` |
| `RoleDefinition` | class | `company_ui.security.authorization` | `(name: "'str'", permissions: "'frozenset[str]'" = frozenset({})) -> 'None'` |
| `RouteBrowserResult` | class | `company_ui.certification.mac_browser` | `(scenario: "'str'", route: "'str'", status: "'str'", detail: "'str'", screenshot: "'str \| None'" = None, duration_ms: "'float \| None'" = None, audit: "'dict[str, object]'" = <factory>, visual_diff: "'dict[str, object] \| None'" = None) -> 'None'` |
| `RouteSmokeResult` | class | `company_ui.certification.runtime_smoke` | `(path: "'str'", status: "'int \| None'", ok: "'bool'", detail: "'str'" = '') -> 'None'` |
| `RowAction` | class | `company_ui.data_table.models` | `(key: "'str'", label: "'str'", icon: "'str \| None'" = None, intent: "'str'" = 'secondary', on_action: "'Callable[[Mapping[str, Any]], Any] \| None'" = None) -> 'None'` |
| `RuntimeConfig` | class | `company_ui.runtime.config` | `(app_name: "'str'", app_version: "'str'" = '0.1.0', environment: "'RuntimeEnvironment'" = 'dev', host: "'str'" = '0.0.0.0', port: "'int'" = 8080, title: "'str \| None'" = None, show_browser: "'bool'" = False, reload: "'bool'" = False, storage_secret_env: "'str'" = 'COMPANY_UI_STORAGE_SECRET', require_storage_secret: "'bool'" = True, secure_session_cookie: "'bool \| None'" = None, same_site: "'str'" = 'strict', session_max_age: "'int \| None'" = None, proxy: "'ProxyConfig'" = <factory>, health_path: "'str'" = '/healthz', readiness_path: "'str'" = '/readyz', diagnostics_path: "'str'" = '/diagnostics', diagnostics_enabled: "'bool'" = False, debug: "'bool'" = False, log_level: "'str'" = 'info', expected_replicas: "'int'" = 1, redis_url_env: "'str'" = 'NICEGUI_REDIS_URL', session_affinity_confirmed_env: "'str'" = 'COMPANY_UI_SESSION_AFFINITY_CONFIRMED', extra_env: "'Mapping[str, str]'" = <factory>) -> 'None'` |
| `RuntimeContractIssue` | class | `company_ui.certification.nicegui_runtime_contract` | `(code: "'str'", detail: "'str'", path: "'str \| None'" = None, line: "'int \| None'" = None) -> 'None'` |
| `RuntimeContractReport` | class | `company_ui.certification.nicegui_runtime_contract` | `(nicegui_version: "'str \| None'", source_issues: "'tuple[RuntimeContractIssue, ...]'", runtime_issues: "'tuple[RuntimeContractIssue, ...]'", factories_checked: "'int'", calls_checked: "'int'") -> 'None'` |
| `RuntimeDefinition` | class | `company_ui.runtime.registry` | `(key: "'str'", use_when: "'str'", rule: "'str'") -> 'None'` |
| `RuntimeDiagnostics` | class | `company_ui.runtime.kernel` | `(active_workspaces: "'int'", application_state_revision: "'int'", workspace_state_revisions: "'Mapping[str, int]'", active_tasks: "'int'", registered_cleanups: "'int'", registered_datasets: "'int'", active_data_sessions: "'int'", workspace_panels: "'int'", registered_extensions: "'int'", event_count: "'int'", latest_event_sequence: "'int'") -> 'None'` |
| `RuntimeDoctor` | class | `company_ui.diagnostics.doctor` | `(config: "'RuntimeConfig'", manifest: "'CompatibilityManifest \| None'" = None)` |
| `RuntimeEnvironment` | class | `company_ui.runtime.config` | `(*values)` |
| `RuntimeEvent` | class | `company_ui.runtime.kernel` | `(sequence: "'int'", kind: "'str'", occurred_at: "'str'", workspace_id: "'str \| None'" = None, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `RuntimeSmokeReport` | class | `company_ui.certification.runtime_smoke` | `(ok: "'bool'", port: "'int'", routes: "'tuple[RouteSmokeResult, ...]'", log_path: "'str'", log_error_patterns: "'tuple[str, ...]'", process_returncode: "'int \| None'") -> 'None'` |
| `RuntimeState` | class | `company_ui.runtime.kernel` | `(initial: "'Mapping[StateNamespace \| str, Mapping[str, Any]] \| None'" = None, history_limit: "'int'" = 500)` |
| `SECURITY_REGISTRY` | constant | `builtins` | `` |
| `SEQUENTIAL_BLUE` | constant | `builtins` | `` |
| `SPACING` | constant | `builtins` | `` |
| `SavedFilterView` | class | `company_ui.integrations.nicegui_interactions` | `(views: "'Sequence[SavedFilterViewSpec]'", value: "'str \| None'" = None, on_change: "'Callable[..., Any] \| None'" = None)` |
| `SavedFilterViewSpec` | class | `company_ui.filters.models` | `(key: "'str'", label: "'str'", values: "'Mapping[str, object]'" = <factory>, is_default: "'bool'" = False) -> 'None'` |
| `ScatterChart` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `ScrollablePanel` | class | `company_ui.layouts.primitives` | `()` |
| `SearchInput` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'" = 'Search', debounce_ms: "'int'" = 250, shortcut: "'str \| None'" = '/', **kwargs)` |
| `SearchInputSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, debounce_ms: "'int'" = 250, clearable: "'bool'" = True, shortcut: "'str \| None'" = '/') -> 'None'` |
| `SearchPage` | class | `company_ui.patterns.pages` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ()) -> "'None'"` |
| `SearchResultSpec` | class | `company_ui.content.models` | `(key: "'str'", title: "'str'", subtitle: "'str \| None'" = None, description: "'str \| None'" = None, icon: "'str \| None'" = None, status: "'str \| None'" = None, metadata: "'Sequence[KeyValueItem]'" = <factory>) -> 'None'` |
| `SearchResults` | class | `company_ui.integrations.nicegui_content` | `(results: "'Sequence[SearchResultSpec]'", on_select: "'Callable[[SearchResultSpec], Any] \| None'" = None)` |
| `Section` | class | `company_ui.layouts.primitives` | `()` |
| `SecurityDefinition` | class | `company_ui.security.registry` | `(key: "'str'", use_when: "'str'", rule: "'str'") -> 'None'` |
| `SecurityHeaders` | class | `company_ui.security.headers` | `(content_type_options: "'str'" = 'nosniff', referrer_policy: "'str'" = 'no-referrer', frame_options: "'str'" = 'DENY', permissions_policy: "'str'" = 'camera=(), microphone=(), geolocation=(), payment=(), usb=()', cross_origin_opener_policy: "'str \| None'" = None, content_security_policy: "'str \| None'" = None, strict_transport_security: "'str \| None'" = None) -> 'None'` |
| `SecurityHeadersMiddleware` | class | `company_ui.security.headers` | `(app, headers: "'SecurityHeaders \| None'" = None)` |
| `SegmentedControl` | class | `company_ui.integrations.nicegui_layout` | `(options: "'dict[str, str]'", value: "'str \| None'" = None, on_change: "'Callable[..., Any] \| None'" = None)` |
| `Select` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", options: "'Sequence[SelectOption] \| dict[str, str]'", value: "'str \| Sequence[str] \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, clearable: "'bool'" = True, searchable: "'bool'" = False, on_change: "'Callable[..., Any] \| None'" = None, _multiple: "'bool'" = False)` |
| `SelectOption` | class | `company_ui.components.models` | `(value: "'str'", label: "'str'", description: "'str \| None'" = None, disabled: "'bool'" = False) -> 'None'` |
| `SelectSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, options: "'Sequence[SelectOption]'" = <factory>, clearable: "'bool'" = True, searchable: "'bool'" = False) -> 'None'` |
| `SelectionMode` | class | `company_ui.data_table.models` | `(*values)` |
| `SemanticVisualData` | class | `company_ui.visualization.semantic` | `(plan: "'SemanticVisualPlan'", result: "'DataResult \| None'", value: "'Any'" = None) -> 'None'` |
| `SemanticVisualPlan` | class | `company_ui.visualization.semantic` | `(spec: "'SemanticVisualSpec'", chart_kind: "'ChartKind \| None'", query: "'DataQuery'", x_field: "'str \| None'", y_fields: "'tuple[str, ...]'", rationale: "'str'") -> 'None'` |
| `SemanticVisualSpec` | class | `company_ui.visualization.semantic` | `(title: "'str'", intent: "'VisualIntent'", dimensions: "'tuple[str, ...]'" = (), metrics: "'tuple[str, ...]'" = (), preferred_kind: "'ChartKind \| None'" = None, sort_descending: "'bool'" = False, limit: "'int \| None'" = None) -> 'None'` |
| `SemanticVisualizationPlanner` | class | `company_ui.visualization.semantic` | `()` |
| `SeriesSpec` | class | `company_ui.visualization.models` | `(key: "'str'", label: "'str'", data: "'Sequence[Any]'", kind: "'ChartKind'" = 'line', x_key: "'str \| None'" = None, y_key: "'str \| None'" = None, stack: "'str \| None'" = None, smooth: "'bool'" = False, marker: "'MarkerShape'" = 'circle', line_style: "'LineStyle'" = 'solid', semantic_color: "'str \| None'" = None, visible: "'bool'" = True, y_axis_index: "'int'" = 0) -> 'None'` |
| `ServerDataTable` | class | `company_ui.integrations.nicegui_data_table` | `(columns: "'Sequence[TableColumn]'", fetch: "'Callable[[TableQuery], Any]'", spec: "'ServerDataTableSpec \| None'" = None, query: "'TableQuery \| None'" = None, **kwargs)` |
| `ServerDataTableSpec` | class | `company_ui.data_table.models` | `(columns: "'tuple[TableColumn, ...]'", row_key: "'str'" = 'id', title: "'str \| None'" = None, description: "'str \| None'" = None, density: "'TableDensity'" = 'compact', selection: "'SelectionMode'" = 'none', pagination: "'PaginationMode'" = 'server', page_size: "'int'" = 50, page_size_options: "'tuple[int, ...]'" = (25, 50, 100, 250), searchable: "'bool'" = True, column_manager: "'bool'" = True, density_control: "'bool'" = True, export_csv: "'bool'" = True, copy_enabled: "'bool'" = True, refresh_enabled: "'bool'" = True, persist_state: "'bool'" = True, persist_key: "'str \| None'" = None, striped: "'bool'" = False, sticky_header: "'bool'" = True, expandable: "'bool'" = False, master_detail: "'bool'" = False, editable: "'bool'" = False, empty_message: "'str'" = 'No records', error_message: "'str'" = 'Unable to load records', cache_pages: "'int'" = 2, cancel_stale_requests: "'bool'" = True, cache_ttl_seconds: "'float'" = 15.0, request_timeout_seconds: "'float \| None'" = 30.0, retry_attempts: "'int'" = 2, retry_base_delay_seconds: "'float'" = 0.15) -> 'None'` |
| `SessionState` | class | `company_ui.state.store` | `(initial: "'dict[str, Any] \| None'" = None, backing: "'MutableMapping[str, Any] \| None'" = None)` |
| `SettingsPage` | class | `company_ui.patterns.pages` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ()) -> "'None'"` |
| `SeverityIndicator` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", intent: "'StatusIntent'")` |
| `ShellConfig` | class | `company_ui.integrations.nicegui_layout` | `(title: "'str'", navigation: "'NavigationModel \| None'" = None, active_route: "'str \| None'" = None, sidebar: "'SidebarMode'" = 'auto', environment: "'str \| None'" = None, on_navigate: "'Callable[[str], None] \| None'" = None, subtitle: "'str \| None'" = None, greeting: "'str \| None'" = None, user_name: "'str \| None'" = None, user_initials: "'str'" = 'U', on_settings: "'Callable[[], None] \| None'" = None, on_about: "'Callable[[], None] \| None'" = None, on_logout: "'Callable[[], None] \| None'" = None, owner: "'str \| None'" = None, on_support: "'Callable[[], None] \| None'" = None, on_feedback: "'Callable[[], None] \| None'" = None, on_docs: "'Callable[[], None] \| None'" = None) -> 'None'` |
| `SidebarMode` | class | `company_ui.layouts.models` | `(*values)` |
| `SidebarPreference` | class | `company_ui.state.models` | `(*values)` |
| `Skeleton` | class | `company_ui.integrations.nicegui_interactions` | `(kind: "'str'" = 'content', rows: "'int'" = 3)` |
| `SkeletonSpec` | class | `company_ui.feedback.models` | `(kind: "'str'" = 'content', rows: "'int'" = 3) -> 'None'` |
| `Slider` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", value: "'float'", minimum: "'float'" = 0, maximum: "'float'" = 100, step: "'float'" = 1, unit: "'str \| None'" = None, disabled: "'bool'" = False, on_change: "'Callable[..., Any] \| None'" = None)` |
| `SliderSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'float'", minimum: "'float'" = 0, maximum: "'float'" = 100, step: "'float'" = 1, unit: "'str \| None'" = None, disabled: "'bool'" = False) -> 'None'` |
| `SortClause` | class | `company_ui.data_engine.models` | `(key: "'str'", descending: "'bool'" = False) -> 'None'` |
| `SortDirection` | class | `company_ui.data_table.models` | `(*values)` |
| `SortSpec` | class | `company_ui.data_table.models` | `(key: "'str'", direction: "'SortDirection'" = 'asc') -> 'None'` |
| `SparklineCell` | class | `company_ui.integrations.nicegui_data_table` | `()` |
| `SpatialMap` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", points: "'Sequence[SpatialPoint]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', **kwargs)` |
| `SpatialPoint` | class | `company_ui.visualization.models` | `(x: "'float'", y: "'float'", value: "'float \| int \| str \| None'" = None, label: "'str \| None'" = None, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `SpecEvaluation` | class | `company_ui.engineering.models` | `(value: "'float \| None'", state: "'SpecState'", nearest_spec_distance: "'float \| None'" = None, normalized_position: "'float \| None'" = None, unit: "'str \| None'" = None) -> 'None'` |
| `SpecLimitIndicator` | class | `company_ui.integrations.nicegui_engineering` | `(value: "'float \| None'" = None, limits: "'LimitBand \| None'" = None, evaluation: "'SpecEvaluation \| None'" = None, decimals: "'int'" = 3)` |
| `SpecLimits` | class | `company_ui.visualization.models` | `(lower: "'float \| None'" = None, upper: "'float \| None'" = None, target: "'float \| None'" = None, lower_label: "'str'" = 'LSL', upper_label: "'str'" = 'USL', target_label: "'str'" = 'Target') -> 'None'` |
| `SpecState` | class | `company_ui.engineering.models` | `(*values)` |
| `Spinner` | class | `company_ui.integrations.nicegui_interactions` | `()` |
| `SplitButton` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", options: "'dict[str, Callable[[], None]]'", icon: "'str \| None'" = None, on_click: "'Callable[..., Any] \| None'" = None, intent: "'ButtonIntent'" = 'primary')` |
| `SplitPane` | class | `company_ui.layouts.primitives` | `(primary_percent: "'int'" = 68)` |
| `Stack` | class | `company_ui.layouts.primitives` | `(direction: "'StackDirection'" = 'vertical', gap: "'Gap'" = 'md', align: "'Align'" = 'stretch')` |
| `StackDirection` | class | `company_ui.layouts.models` | `(*values)` |
| `StackedBarChart` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `StaleResponseGuard` | class | `company_ui.async_tools.runtime` | `()` |
| `StateIllustration` | class | `company_ui.integrations.nicegui_visual_assets` | `(key: "'str'", label: "'str \| None'" = None) -> 'None'` |
| `StateKey` | class | `company_ui.runtime.kernel` | `(name: "'str'", namespace: "'StateNamespace'" = 'workspace', default: "'T \| object'" = <object object>, validator: "'Validator \| None'" = None) -> 'None'` |
| `StateKind` | class | `company_ui.feedback.models` | `(*values)` |
| `StateMutation` | class | `company_ui.runtime.kernel` | `(namespace: "'StateNamespace'", key: "'str'", old: "'Any'", new: "'Any'", revision: "'int'", source: "'str'", old_present: "'bool'" = True, new_present: "'bool'" = True) -> 'None'` |
| `StateNamespace` | class | `company_ui.runtime.kernel` | `(*values)` |
| `StateScope` | class | `company_ui.state.models` | `(*values)` |
| `StateSnapshot` | class | `company_ui.runtime.kernel` | `(revision: "'int'", values: "'Mapping[str, Mapping[str, Any]]'") -> 'None'` |
| `StateStore` | class | `company_ui.state.store` | `(initial: "'dict[str, Any] \| None'" = None, backing: "'MutableMapping[str, Any] \| None'" = None)` |
| `StateView` | class | `company_ui.integrations.nicegui_interactions` | `(spec: "'StateViewSpec'", on_action: "'Callable[..., Any] \| None'" = None, on_secondary_action: "'Callable[..., Any] \| None'" = None)` |
| `StateViewSpec` | class | `company_ui.feedback.models` | `(kind: "'StateKind'", title: "'str'", message: "'str \| None'" = None, action_label: "'str \| None'" = None, secondary_action_label: "'str \| None'" = None, error_id: "'str \| None'" = None, compact: "'bool'" = False) -> 'None'` |
| `StatusBadge` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", intent: "'StatusIntent'" = 'neutral', icon: "'str \| None'" = None)` |
| `StatusCell` | class | `company_ui.integrations.nicegui_data_table` | `()` |
| `StatusIntent` | class | `company_ui.components.models` | `(*values)` |
| `StepSpec` | class | `company_ui.content.models` | `(key: "'str'", label: "'str'", description: "'str \| None'" = None, state: "'StepState'" = 'upcoming', icon: "'str \| None'" = None) -> 'None'` |
| `StepState` | class | `company_ui.content.models` | `(*values)` |
| `Stepper` | class | `company_ui.integrations.nicegui_content` | `(steps: "'Sequence[StepSpec]'", value: "'str \| None'" = None, vertical: "'bool'" = False)` |
| `StickyPanel` | class | `company_ui.layouts.primitives` | `()` |
| `SurfaceGrid` | class | `company_ui.layouts.primitives` | `()` |
| `SurfaceSpec` | class | `company_ui.components.models` | `(variant: "'SurfaceVariant'" = 'panel', interactive: "'bool'" = False, selected: "'bool'" = False, title: "'str \| None'" = None) -> 'None'` |
| `SurfaceVariant` | class | `company_ui.components.models` | `(*values)` |
| `SvgIcon` | class | `company_ui.integrations.nicegui_visual_assets` | `(key: "'str'", size: "'IconSize \| str'" = 'md', label: "'str \| None'" = None) -> 'None'` |
| `Switch` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", checked: "'bool'" = False, description: "'str \| None'" = None, disabled: "'bool'" = False, on_change: "'Callable[..., Any] \| None'" = None)` |
| `SwitchSpec` | class | `company_ui.components.models` | `(label: "'str'", checked: "'bool'" = False, description: "'str \| None'" = None, disabled: "'bool'" = False) -> 'None'` |
| `TABLE_REGISTRY` | constant | `builtins` | `` |
| `TTLCache` | class | `company_ui.performance.cache` | `(maxsize: "'int'" = 128, ttl_seconds: "'float'" = 60.0)` |
| `TYPOGRAPHY` | constant | `builtins` | `` |
| `TabSpec` | class | `company_ui.navigation.models` | `(id: "'str'", label: "'str'", icon: "'str \| None'" = None, badge: "'str \| int \| None'" = None, lazy: "'bool'" = True, url_segment: "'str \| None'" = None, disabled: "'bool'" = False) -> 'None'` |
| `TabState` | class | `company_ui.state.store` | `(initial: "'dict[str, Any] \| None'" = None, backing: "'MutableMapping[str, Any] \| None'" = None)` |
| `TableColumn` | class | `company_ui.data_table.models` | `(key: "'str'", label: "'str'", kind: "'ColumnKind'" = 'text', width: "'int \| None'" = None, min_width: "'int'" = 80, max_width: "'int \| None'" = None, sortable: "'bool'" = True, filterable: "'bool'" = True, resizable: "'bool'" = True, visible: "'bool'" = True, pinned: "'PinPosition'" = 'none', align: "'str \| None'" = None, decimals: "'int \| None'" = None, unit: "'str \| None'" = None, tooltip: "'str \| None'" = None, editable: "'bool'" = False, required: "'bool'" = False, rules: "'tuple[ConditionalRule, ...]'" = (), priority: "'str'" = 'normal', status_map: "'Mapping[str, str]'" = <factory>) -> 'None'` |
| `TableColumnManager` | class | `company_ui.integrations.nicegui_data_table` | `(columns: "'Sequence[TableColumn]'", table: '"\'DataTable \| None\'"' = None)` |
| `TableContextMenu` | class | `company_ui.integrations.nicegui_data_table` | `(actions: "'Sequence[RowAction]'" = ())` |
| `TableDefinition` | class | `company_ui.data_table.registry` | `(key: 'str', public_name: 'str', purpose: 'str', use_when: 'tuple[str, ...]', avoid_when: 'tuple[str, ...]' = ()) -> 'None'` |
| `TableDensity` | class | `company_ui.data_table.models` | `(*values)` |
| `TableDensitySelector` | class | `company_ui.integrations.nicegui_data_table` | `(density: "'TableDensity'" = 'compact', table: '"\'DataTable \| None\'"' = None)` |
| `TablePreset` | class | `company_ui.data_table.models` | `(name: "'str'", visible_columns: "'tuple[str, ...]'" = (), pinned_left: "'tuple[str, ...]'" = (), pinned_right: "'tuple[str, ...]'" = (), density: "'TableDensity'" = 'compact', sorts: "'tuple[SortSpec, ...]'" = (), filters: "'tuple[FilterSpec, ...]'" = ()) -> 'None'` |
| `TablePresetSelector` | class | `company_ui.integrations.nicegui_data_table` | `(presets: "'Sequence[TablePreset]'", table: "'DataTable \| None'" = None, on_select: "'Callable[[TablePreset], Any] \| None'" = None)` |
| `TableQuery` | class | `company_ui.data_table.models` | `(page: "'int'" = 1, page_size: "'int'" = 50, search: "'str'" = '', sorts: "'tuple[SortSpec, ...]'" = (), filters: "'tuple[FilterSpec, ...]'" = ()) -> 'None'` |
| `TableQueryEngine` | class | `company_ui.data_table.engine` | `(rows: "'Iterable[Mapping[str, Any]]'", searchable_columns: "'Sequence[str] \| None'" = None, max_cached_queries: "'int'" = 32, build_search_index: "'bool'" = True)` |
| `TableResult` | class | `company_ui.data_table.models` | `(rows: "'tuple[Mapping[str, Any], ...]'", total: "'int'", page: "'int'" = 1, page_size: "'int'" = 50) -> 'None'` |
| `TableRowActions` | class | `company_ui.integrations.nicegui_data_table` | `(actions: "'Sequence[RowAction]'" = ())` |
| `TableSelectionBar` | class | `company_ui.integrations.nicegui_data_table` | `(actions: "'Sequence[BulkAction]'" = (), table: '"\'DataTable \| None\'"' = None)` |
| `TableState` | class | `company_ui.data_table.models` | `(density: "'TableDensity'" = 'compact', search: "'str'" = '', selected_keys: "'set[Any]'" = <factory>, expanded_keys: "'set[Any]'" = <factory>, visible_columns: "'list[str]'" = <factory>, column_order: "'list[str]'" = <factory>, column_widths: "'dict[str, int]'" = <factory>, pinned_left: "'list[str]'" = <factory>, pinned_right: "'list[str]'" = <factory>, sorts: "'list[SortSpec]'" = <factory>, filters: "'list[FilterSpec]'" = <factory>, page: "'int'" = 1, page_size: "'int'" = 50, scroll_row_index: "'int'" = 0) -> 'None'` |
| `TableToolbar` | class | `company_ui.integrations.nicegui_data_table` | `(table: '"\'DataTable \| None\'"' = None, searchable: "'bool'" = True, columns: "'bool'" = True, density: "'bool'" = True, export: "'bool'" = True, refresh: "'bool'" = True)` |
| `Tabs` | class | `company_ui.integrations.nicegui_layout` | `(specs: "'tuple[TabSpec, ...]'", value: "'str \| None'" = None)` |
| `Tag` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", intent: "'StatusIntent'" = 'neutral', icon: "'str \| None'" = None)` |
| `TaskStatus` | class | `company_ui.async_tools.models` | `(*values)` |
| `TextArea` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", value: "'str \| None'" = None, placeholder: "'str \| None'" = None, rows: "'int'" = 4, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, on_change: "'Callable[..., Any] \| None'" = None)` |
| `TextAreaSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, rows: "'int'" = 4, maxlength: "'int \| None'" = None) -> 'None'` |
| `TextInput` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", value: "'str \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, clearable: "'bool'" = False, password: "'bool'" = False, leading_icon: "'str \| None'" = None, on_change: "'Callable[..., Any] \| None'" = None)` |
| `TextInputSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, clearable: "'bool'" = False, password: "'bool'" = False, maxlength: "'int \| None'" = None) -> 'None'` |
| `ThemeMode` | class | `company_ui.design.system` | `(*values)` |
| `ThemeService` | class | `company_ui.services.core` | `(mode: "'ThemeMode'" = 'system', density: "'str'" = 'compact', sink: "'Callable[[ThemeMode, str], Any] \| None'" = None)` |
| `ThresholdSpec` | class | `company_ui.visualization.models` | `(value: "'float'", label: "'str'", intent: "'AnnotationIntent'" = 'warning', line_style: "'LineStyle'" = 'dashed') -> 'None'` |
| `Throttler` | class | `company_ui.async_tools.runtime` | `(interval_seconds: "'float'")` |
| `TimePicker` | class | `company_ui.integrations.nicegui_components` | `(label: "'str'", value: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False)` |
| `TimePickerSpec` | class | `company_ui.components.models` | `(label: "'str'", value: "'object \| None'" = None, placeholder: "'str \| None'" = None, description: "'str \| None'" = None, error: "'str \| None'" = None, required: "'bool'" = False, disabled: "'bool'" = False, readonly: "'bool'" = False, size: "'ComponentSize'" = 'medium', width: "'InputWidth'" = 'auto', leading_icon: "'str \| None'" = None, trailing_icon: "'str \| None'" = None, use_24_hour: "'bool'" = True) -> 'None'` |
| `TimelineChart` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", series: "'Sequence[SeriesSpec]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', x_axis: "'AxisSpec \| None'" = None, y_axis: "'AxisSpec \| None'" = None, thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, **kwargs)` |
| `Toast` | class | `company_ui.integrations.nicegui_interactions` | `(message: "'str'", intent: "'FeedbackIntent'" = 'info', duration_ms: "'int'" = 3500, dismissible: "'bool'" = True)` |
| `ToastPlacement` | class | `company_ui.feedback.models` | `(*values)` |
| `ToastSpec` | class | `company_ui.feedback.models` | `(message: "'str'", intent: "'FeedbackIntent'" = 'info', duration_ms: "'int'" = 3500, placement: "'ToastPlacement'" = 'top-right', dismissible: "'bool'" = True, action_label: "'str \| None'" = None) -> 'None'` |
| `ToolbarGroup` | class | `company_ui.layouts.primitives` | `()` |
| `Tooltip` | class | `company_ui.integrations.nicegui_interactions` | `(text: "'str'", delay_ms: "'int'" = 450)` |
| `TooltipSpec` | class | `company_ui.overlays.models` | `(text: "'str'", delay_ms: "'int'" = 450, max_width: "'int'" = 320) -> 'None'` |
| `TreeNode` | class | `company_ui.content.models` | `(key: "'str'", label: "'str'", children: '"Sequence[\'TreeNode\']"' = <factory>, icon: "'str \| None'" = None, disabled: "'bool'" = False, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `TreeView` | class | `company_ui.integrations.nicegui_content` | `(nodes: "'Sequence[TreeNode]'", selected: "'str \| None'" = None, on_select: "'Callable[..., Any] \| None'" = None, tick_strategy: "'str \| None'" = None)` |
| `TrendDirection` | class | `company_ui.content.models` | `(*values)` |
| `TrendIndicator` | class | `company_ui.integrations.nicegui_content` | `(value: "'str'", trend: "'TrendDirection'" = 'unknown', intent: "'StatusIntent'" = 'neutral')` |
| `TrustedProxyPolicy` | class | `company_ui.security.models` | `(networks: "'tuple[str, ...]'" = ('127.0.0.1/32', '::1/128')) -> 'None'` |
| `UploadPolicy` | class | `company_ui.security.uploads` | `(max_bytes: "'int'" = 26214400, allowed_extensions: "'frozenset[str]'" = frozenset({'.csv', '.jpeg', '.jpg', '.json', '.pdf', '.png', '.txt', '.xlsx'}), allowed_media_types: "'frozenset[str]'" = frozenset({'application/json', 'application/pdf', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'image/jpeg', 'image/png', 'text/csv', 'text/plain'}), reject_active_content: "'bool'" = True) -> 'None'` |
| `UrlField` | class | `company_ui.state.url` | `(key: "'str'", kind: "'type'" = <class 'str'>, multiple: "'bool'" = False, default: "'Any'" = None) -> 'None'` |
| `UrlState` | class | `company_ui.state.url` | `(fields: "'Sequence[UrlField]'" = ())` |
| `UserFacingError` | class | `company_ui.services.operations` | `(error_id: "'str'", message: "'str'", retryable: "'bool'" = False) -> 'None'` |
| `UserMenu` | class | `company_ui.integrations.nicegui_layout` | `(initials: "'str'" = 'U', user_name: "'str \| None'" = None, greeting: "'str \| None'" = None, on_preferences: "'Callable[[], None] \| None'" = None, on_about: "'Callable[[], None] \| None'" = None, on_logout: "'Callable[[], None] \| None'" = None)` |
| `UserPreferences` | class | `company_ui.state.models` | `(theme: "'str'" = 'system', density: "'str'" = 'compact', sidebar: "'SidebarPreference'" = 'expanded', table_states: "'Mapping[str, Mapping[str, Any]]'" = <factory>, filter_views: "'Mapping[str, Mapping[str, Any]]'" = <factory>, favorites: "'tuple[str, ...]'" = (), recent_entities: "'tuple[str, ...]'" = ()) -> 'None'` |
| `VISUALIZATION_REGISTRY` | constant | `builtins` | `` |
| `VISUAL_ROOT` | constant | `pathlib._local` | `` |
| `ValidationIssue` | class | `company_ui.forms.models` | `(field: "'str'", message: "'str'", severity: "'ValidationSeverity'" = 'error', code: "'str \| None'" = None) -> 'None'` |
| `ValidationMessage` | class | `company_ui.integrations.nicegui_interactions` | `(message: "'str'")` |
| `ValidationSeverity` | class | `company_ui.forms.models` | `(*values)` |
| `ValidationSummary` | class | `company_ui.integrations.nicegui_interactions` | `(spec: "'ValidationSummarySpec'")` |
| `ValidationSummarySpec` | class | `company_ui.forms.models` | `(issues: "'Sequence[ValidationIssue]'", title: "'str'" = 'Please review the highlighted fields') -> 'None'` |
| `ValidatorConfig` | class | `company_ui.ai.validator` | `(exclude_dirs: "'tuple[str, ...]'" = ('.git', '.venv', 'venv', '__pycache__', 'build', 'dist', 'company_ui'), page_dirs: "'tuple[str, ...]'" = ('pages', 'views', 'screens'), warnings_as_errors: "'bool'" = False) -> 'None'` |
| `ViewportProfile` | class | `company_ui.design.responsive` | `(key: "'str'", width: "'int'", height: "'int'", tier: "'str'") -> 'None'` |
| `VisualAuditIssue` | class | `company_ui.certification.visual_audit` | `(code: "'str'", message: "'str'", path: "'str \| None'" = None) -> 'None'` |
| `VisualIntent` | class | `company_ui.visualization.semantic` | `(*values)` |
| `WaferComparisonMap` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", affected: "'Sequence[WaferPoint]'", control: "'Sequence[WaferPoint]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard')` |
| `WaferMap` | class | `company_ui.integrations.nicegui_visualization` | `(title: "'str'", points: "'Sequence[WaferPoint]'", description: "'str \| None'" = None, size: "'ChartSize'" = 'standard', **kwargs)` |
| `WaferPoint` | class | `company_ui.visualization.models` | `(x: "'float'", y: "'float'", value: "'float \| int \| str \| None'" = None, die_x: "'int \| None'" = None, die_y: "'int \| None'" = None, status: "'str \| None'" = None, metadata: "'Mapping[str, Any]'" = <factory>) -> 'None'` |
| `Well` | class | `company_ui.integrations.nicegui_components` | `()` |
| `WizardPage` | class | `company_ui.patterns.pages` | `(title: "'str'", description: "'str \| None'" = None, breadcrumbs: "'tuple[Breadcrumb, ...]'" = ()) -> "'None'"` |
| `WorkspaceBreakpoint` | class | `company_ui.workspace.models` | `(*values)` |
| `WorkspaceLayoutEngine` | class | `company_ui.workspace.engine` | `() -> "'None'"` |
| `WorkspaceLayoutSnapshot` | class | `company_ui.workspace.models` | `(schema_version: "'int'", revision: "'int'", panels: "'tuple[PanelSpec, ...]'", placements: "'tuple[GridPlacement, ...]'") -> 'None'` |
| `WorkspacePreferenceService` | class | `company_ui.services.preferences` | `(backing: "'MutableMapping[str, Any]'", key: "'str'" = 'company_ui_workspaces', max_recent: "'int'" = 20)` |
| `WorkspaceRuntime` | class | `company_ui.runtime.kernel` | `(workspace_id: "'str'", data_engine: "'DataEngine \| None'" = None, initial_state: "'Mapping[StateNamespace \| str, Mapping[str, Any]] \| None'" = None)` |
| `WorkspaceSnapshot` | class | `company_ui.runtime.kernel` | `(workspace_id: "'str'", state: "'StateSnapshot'", layout: "'WorkspaceLayoutSnapshot'", data_sessions: "'Mapping[str, tuple[str, DataSessionSnapshot]]'") -> 'None'` |
| `ai` | module | `builtins` | `` |
| `analytics` | module | `builtins` | `` |
| `annotations` | constant | `__future__` | `` |
| `application_snapshot_from_dict` | function | `company_ui.runtime.persistence` | `(payload: "'Mapping[str, Any]'") -> "'ApplicationSnapshot'"` |
| `application_snapshot_to_dict` | function | `company_ui.runtime.persistence` | `(snapshot: "'ApplicationSnapshot'") -> "'dict[str, Any]'"` |
| `apply_query` | function | `company_ui.data_table.engine` | `(rows: "'Iterable[Mapping[str, Any]]'", query: "'TableQuery'", searchable_columns: "'Sequence[str] \| None'" = None) -> "'TableResult'"` |
| `approve_visual_baseline` | function | `company_ui.certification.mac_baseline` | `(output_dir: "'Path'", baseline_dir: "'Path'", force: "'bool'" = False) -> "'BaselineApproval'"` |
| `apps` | module | `builtins` | `` |
| `async_tools` | module | `builtins` | `` |
| `audit_framework_visual_sources` | function | `company_ui.certification.visual_audit` | `(root: "'str \| Path'") -> "'tuple[VisualAuditIssue, ...]'"` |
| `audit_visual_css` | function | `company_ui.certification.visual_audit` | `(css: "'str'") -> "'tuple[VisualAuditIssue, ...]'"` |
| `authorization` | module | `builtins` | `` |
| `box_summary` | function | `company_ui.visualization.engine` | `(values: "'Iterable[float]'") -> "'dict[str, float] \| None'"` |
| `build_certification_app` | function | `company_ui.certification.apps` | `() -> "'AppShell'"` |
| `build_component_css` | function | `company_ui.components.css` | `() -> "'str'"` |
| `build_component_gallery` | function | `company_ui.certification.apps` | `() -> "'AppShell'"` |
| `build_constitution_css` | function | `company_ui.design.constitution_css` | `() -> "'str'"` |
| `build_content_css` | function | `company_ui.content.css` | `() -> "'str'"` |
| `build_data_table_css` | function | `company_ui.data_table.css` | `() -> "'str'"` |
| `build_design_system` | function | `company_ui.design.system` | `() -> "'DesignSystem'"` |
| `build_echarts_options` | function | `company_ui.visualization.options` | `(spec: "'ChartPanelSpec'", series: "'Sequence[SeriesSpec]'", thresholds: "'Sequence[ThresholdSpec]'" = (), spec_limits: "'SpecLimits \| None'" = None, theme: "'ChartTheme \| None'" = None) -> "'dict[str, Any]'"` |
| `build_engineering_css` | function | `company_ui.engineering.css` | `() -> "'str'"` |
| `build_interaction_css` | function | `company_ui.interaction_css` | `() -> 'str'` |
| `build_layout_css` | function | `company_ui.layouts.css` | `() -> "'str'"` |
| `build_provenance` | function | `company_ui.supply_chain` | `(artifact: "'str \| Path \| None'" = None) -> "'dict[str, Any]'"` |
| `build_spdx_sbom` | function | `company_ui.supply_chain` | `(name: "'str'" = 'company-ui', namespace: "'str \| None'" = None) -> "'dict[str, Any]'"` |
| `build_visual_asset_css` | function | `company_ui.visual.css` | `() -> 'str'` |
| `build_visualization_css` | function | `company_ui.visualization.css` | `() -> 'str'` |
| `cache` | module | `builtins` | `` |
| `canonical_viewport` | function | `company_ui.design.responsive` | `(key: "'str'") -> "'ViewportProfile'"` |
| `certification` | module | `builtins` | `` |
| `chart_theme` | function | `company_ui.visualization.theme` | `(mode: "'str'" = 'light') -> "'ChartTheme'"` |
| `combined_css` | function | `company_ui.certification.engine` | `() -> "'str'"` |
| `compare_populations` | function | `company_ui.engineering.analytics` | `(affected: "'PopulationSummary'", control: "'PopulationSummary'") -> "'PopulationComparison'"` |
| `compatibility` | module | `builtins` | `` |
| `components` | module | `builtins` | `` |
| `compositions` | module | `builtins` | `` |
| `config` | module | `builtins` | `` |
| `configure_structured_logging` | function | `company_ui.diagnostics.logging` | `(level: "'str'" = 'INFO', logger_name: "'str'" = 'company_ui') -> "'logging.Logger'"` |
| `content` | module | `builtins` | `` |
| `convenience_registry` | module | `builtins` | `` |
| `correlation` | module | `builtins` | `` |
| `coverage_summary` | function | `company_ui.certification.mac_coverage` | `() -> "'dict[str, object]'"` |
| `css` | module | `builtins` | `` |
| `data_engine` | module | `builtins` | `` |
| `data_table` | module | `builtins` | `` |
| `dataclass` | function | `dataclasses` | `(cls = None, init = True, repr = True, eq = True, order = False, unsafe_hash = False, frozen = False, match_args = True, kw_only = False, slots = False, weakref_slot = False)` |
| `deserialize_application_snapshot` | function | `company_ui.runtime.persistence` | `(value: "'str'") -> "'ApplicationSnapshot'"` |
| `design` | module | `builtins` | `` |
| `diagnostics` | module | `builtins` | `` |
| `doctor` | module | `builtins` | `` |
| `engine` | module | `builtins` | `` |
| `engineering` | module | `builtins` | `` |
| `evaluate_spec` | function | `company_ui.engineering.analytics` | `(value: "'float \| None'", limits: "'LimitBand'") -> "'SpecEvaluation'"` |
| `evidence_balance` | function | `company_ui.engineering.analytics` | `(items: "'Iterable[EvidenceItem]'") -> "'EvidenceBalance'"` |
| `exhaustive_scenarios` | function | `company_ui.certification.mac_browser` | `(include_edge: "'bool'" = True) -> "'tuple[BrowserScenario, ...]'"` |
| `export_csv` | function | `company_ui.data_table.engine` | `(rows: "'Iterable[Mapping[str, Any]]'", columns: "'Sequence[TableColumn]'") -> "'str'"` |
| `export_digest` | function | `company_ui.governance.public_api` | `(snapshot: "'dict[str, dict[str, Any]] \| None'" = None) -> "'str'"` |
| `export_names` | function | `company_ui.governance.public_api` | `() -> "'tuple[str, ...]'"` |
| `extensions` | module | `builtins` | `` |
| `feedback` | module | `builtins` | `` |
| `field` | function | `dataclasses` | `(default = <dataclasses._MISSING_TYPE object>, default_factory = <dataclasses._MISSING_TYPE object>, init = True, repr = True, hash = None, compare = True, metadata = None, kw_only = <dataclasses._MISSING_TYPE object>)` |
| `filters` | module | `builtins` | `` |
| `format_cell` | function | `company_ui.data_table.engine` | `(value: "'Any'", column: "'TableColumn'") -> "'str'"` |
| `forms` | module | `builtins` | `` |
| `get_ai_construction` | function | `company_ui.ai.registry` | `(key: "'str'") -> "'AiConstructionDefinition'"` |
| `get_component` | function | `company_ui.components.registry` | `(key: "'str'") -> "'ComponentDefinition'"` |
| `get_content` | function | `company_ui.content.registry` | `(key: "'str'") -> "'ContentDefinition'"` |
| `get_convenience` | function | `company_ui.convenience_registry` | `(key: "'str'") -> "'ConvenienceDefinition'"` |
| `get_correlation_id` | function | `company_ui.diagnostics.correlation` | `() -> "'str \| None'"` |
| `get_engineering` | function | `company_ui.engineering.registry` | `(name: "'str'") -> "'EngineeringDefinition'"` |
| `get_icon` | function | `company_ui.visual.registry` | `(key: "'str'") -> "'IconDefinition'"` |
| `get_illustration` | function | `company_ui.visual.registry` | `(key: "'str'") -> "'IllustrationDefinition'"` |
| `get_interaction` | function | `company_ui.interaction_registry` | `(key: "'str'") -> "'InteractionDefinition'"` |
| `get_pattern` | function | `company_ui.patterns.registry` | `(pattern: "'PagePattern \| str'") -> "'PatternDefinition'"` |
| `get_performance` | function | `company_ui.performance.registry` | `(key)` |
| `get_runtime_definition` | function | `company_ui.runtime.registry` | `(key: "'str'") -> "'RuntimeDefinition'"` |
| `get_security_definition` | function | `company_ui.security.registry` | `(key: "'str'") -> "'SecurityDefinition'"` |
| `get_table` | function | `company_ui.data_table.registry` | `(key: 'str') -> 'company_ui.data_table.registry.TableDefinition'` |
| `get_visualization` | function | `company_ui.visualization.registry` | `(name: "'str'") -> "'VisualizationDefinition'"` |
| `governance` | module | `builtins` | `` |
| `headers` | module | `builtins` | `` |
| `health` | module | `builtins` | `` |
| `histogram` | function | `company_ui.visualization.engine` | `(values: "'Iterable[float]'", bins: "'int'" = 10) -> "'list[dict[str, float \| int]]'"` |
| `hypothesis_rank_score` | function | `company_ui.engineering.analytics` | `(hypothesis: "'RcaHypothesis'") -> "'float'"` |
| `icon_path` | function | `company_ui.visual.registry` | `(key: "'str'") -> "'Path'"` |
| `illustration_path` | function | `company_ui.visual.registry` | `(key: "'str'") -> "'Path'"` |
| `install_ai_materials` | function | `company_ui.ai.scaffold` | `(destination: "'str \| Path'", overwrite: "'bool'" = False) -> "'tuple[Path, ...]'"` |
| `install_visual_assets_css` | function | `company_ui.integrations.nicegui_visual_assets` | `()` |
| `installed_version` | function | `company_ui.runtime.compatibility` | `(distribution: "'str'") -> "'str \| None'"` |
| `integrations` | module | `builtins` | `` |
| `interaction_css` | module | `builtins` | `` |
| `interaction_registry` | module | `builtins` | `` |
| `is_secret_key` | function | `company_ui.security.redaction` | `(key: "'str'", extra_keys: "'frozenset[str]'" = frozenset({})) -> "'bool'"` |
| `iter_ui_factory_calls` | function | `company_ui.certification.nicegui_runtime_contract` | `(root: "'Path \| None'" = None) -> "'Iterable[tuple[Path, ast.Call, str, tuple[str, ...]]]'"` |
| `jobs` | module | `builtins` | `` |
| `kernel` | module | `builtins` | `` |
| `layouts` | module | `builtins` | `` |
| `live_checks` | module | `builtins` | `` |
| `live_component_coverage` | function | `company_ui.certification.mac_coverage` | `() -> "'tuple[ComponentCoverage, ...]'"` |
| `live_lab` | module | `builtins` | `` |
| `live_models` | module | `builtins` | `` |
| `load_ai_manifest` | function | `company_ui.ai.manifest` | `() -> "'dict'"` |
| `load_framework_catalog` | function | `company_ui.ai.catalog` | `() -> "'dict'"` |
| `log_event` | function | `company_ui.diagnostics.logging` | `(logger: "'logging.Logger'", level: "'int'", message: "'str'", **context: "'Any'") -> "'None'"` |
| `logging` | module | `builtins` | `` |
| `mac_baseline` | module | `builtins` | `` |
| `mac_browser` | module | `builtins` | `` |
| `mac_certify` | module | `builtins` | `` |
| `mac_coverage` | module | `builtins` | `` |
| `mac_lab` | module | `builtins` | `` |
| `mac_lab_css` | module | `builtins` | `` |
| `mac_preflight` | module | `builtins` | `` |
| `min_length` | function | `company_ui.forms.validation` | `(length: "'int'", message: "'str \| None'" = None)` |
| `models` | module | `builtins` | `` |
| `navigation` | module | `builtins` | `` |
| `new_correlation_id` | function | `company_ui.diagnostics.correlation` | `() -> "'str'"` |
| `nicegui_runtime_contract` | module | `builtins` | `` |
| `normalize_shortcut` | function | `company_ui.services.keyboard` | `(value: "'str'") -> "'str'"` |
| `numeric_range` | function | `company_ui.forms.validation` | `(minimum: "'float \| None'" = None, maximum: "'float \| None'" = None, message: "'str \| None'" = None)` |
| `overlays` | module | `builtins` | `` |
| `pareto` | function | `company_ui.visualization.engine` | `(rows: "'Iterable[Mapping[str, Any]]'", category_key: "'str'", value_key: "'str'") -> "'list[dict[str, Any]]'"` |
| `pattern` | function | `company_ui.forms.validation` | `(regex: "'str'", message: "'str'" = 'Invalid format')` |
| `patterns` | module | `builtins` | `` |
| `percentile` | function | `company_ui.engineering.analytics` | `(values: "'Sequence[float]'", q: "'float'") -> "'float \| None'"` |
| `performance` | module | `builtins` | `` |
| `persistence` | module | `builtins` | `` |
| `probe_auth` | function | `company_ui.certification.live_checks` | `(config: "'LiveCertificationConfig'") -> "'list[LiveGateResult]'"` |
| `probe_browser` | function | `company_ui.certification.live_checks` | `(config: "'BrowserProbeConfig'", target_url: "'str'") -> "'list[LiveGateResult]'"` |
| `probe_health` | function | `company_ui.certification.live_checks` | `(config: "'LiveCertificationConfig'") -> "'list[LiveGateResult]'"` |
| `probe_http` | function | `company_ui.certification.live_checks` | `(config: "'LiveCertificationConfig'") -> "'list[LiveGateResult]'"` |
| `probe_load` | function | `company_ui.certification.live_checks` | `(load: "'LoadProbeConfig'", headers: "'dict[str, str]'") -> "'LiveGateResult'"` |
| `probe_websocket` | function | `company_ui.certification.live_checks` | `(config: "'LiveCertificationConfig'") -> "'LiveGateResult'"` |
| `rank_commonalities` | function | `company_ui.engineering.analytics` | `(items: "'Iterable[CommonalityObservation]'") -> "'list[CommonalityObservation]'"` |
| `rank_hypotheses` | function | `company_ui.engineering.analytics` | `(hypotheses: "'Iterable[RcaHypothesis]'") -> "'list[RcaHypothesis]'"` |
| `read_ai_guide` | function | `company_ui.ai.scaffold` | `(name: "'str'") -> "'str'"` |
| `redact` | function | `company_ui.security.redaction` | `(value: "'Any'", extra_keys: "'frozenset[str]'" = frozenset({}), replacement: "'str'" = '[REDACTED]') -> "'Any'"` |
| `redact_text` | function | `company_ui.security.redaction` | `(text: "'str'", replacement: "'str'" = '[REDACTED]') -> "'str'"` |
| `redaction` | module | `builtins` | `` |
| `register_mac_lab_pages` | function | `company_ui.certification.mac_lab` | `() -> "'None'"` |
| `registry` | module | `builtins` | `` |
| `render_icon_svg` | function | `company_ui.visual.renderer` | `(key: "'str'", size: "'IconSize \| str'" = 'md', label: "'str \| None'" = None, css_class: "'str'" = 'cui-icon') -> "'str'"` |
| `render_illustration_svg` | function | `company_ui.visual.renderer` | `(key: "'str'", label: "'str \| None'" = None, css_class: "'str'" = 'cui-illustration') -> "'str'"` |
| `required` | function | `company_ui.forms.validation` | `(message: "'str'" = 'Required') -> "'Callable[[object \| None], str \| None]'"` |
| `required_visual_classes` | function | `company_ui.certification.mac_coverage` | `() -> "'tuple[tuple[str, str], ...]'"` |
| `reset_correlation_id` | function | `company_ui.diagnostics.correlation` | `(token: "'contextvars.Token'") -> "'None'"` |
| `resolve_icon_key` | function | `company_ui.visual.registry` | `(key: "'str'") -> "'str'"` |
| `run_blocking` | function | `company_ui.performance.runtime` | `(func: "'Callable[..., T]'", *args: "'Any'", **kwargs: "'Any'") -> "'T'"` |
| `run_certification` | function | `company_ui.certification.engine` | `(root: "'str \| Path \| None'" = None, require_nicegui: "'bool'" = False) -> "'CertificationReport'"` |
| `run_certification_app` | function | `company_ui.certification.apps` | `() -> "'None'"` |
| `run_component_gallery` | function | `company_ui.certification.apps` | `() -> "'None'"` |
| `run_gold_certification` | function | `company_ui.certification.live_checks` | `(config: "'LiveCertificationConfig'", root: "'str \| Path \| None'" = None) -> "'GoldCertificationReport'"` |
| `run_governance` | function | `company_ui.governance.engine` | `(root: "'str \| Path'" = '.') -> "'GovernanceReport'"` |
| `run_installed_runtime_contract` | function | `company_ui.certification.nicegui_runtime_contract` | `(root: "'Path \| None'" = None) -> "'RuntimeContractReport'"` |
| `run_mac_browser_matrix` | function | `company_ui.certification.mac_browser` | `(base_url: "'str'", output_dir: "'Path'", baseline_dir: "'Path \| None'" = None, exhaustive: "'bool'" = False, include_edge: "'bool'" = True, browser_executables: "'dict[str, str] \| None'" = None, report_name: "'str'" = 'MAC_BROWSER_REPORT.json') -> "'MacBrowserReport'"` |
| `run_mac_certification` | function | `company_ui.certification.mac_certify` | `(output_dir: "'Path'", baseline_dir: "'Path \| None'" = None, root: "'Path \| None'" = None, port: "'int'" = 8080, exhaustive: "'bool'" = False, include_edge: "'bool'" = True, require_edge: "'bool'" = False, require_baseline: "'bool'" = False, load_requests: "'int'" = 120, load_concurrency: "'int'" = 12) -> "'MacCertificationReport'"` |
| `run_mac_lab` | function | `company_ui.certification.mac_lab` | `(host: "'str'" = '127.0.0.1', port: "'int'" = 8080, show: "'bool'" = False) -> "'None'"` |
| `run_preflight` | function | `company_ui.certification.mac_preflight` | `(port: "'int'" = 8080, require_chrome: "'bool'" = True, require_edge: "'bool'" = False) -> "'tuple[PreflightCheck, ...]'"` |
| `run_runtime_smoke` | function | `company_ui.certification.runtime_smoke` | `(output_dir: "'Path \| str \| None'" = None, port: "'int \| None'" = None, python_executable: "'str \| None'" = None) -> "'RuntimeSmokeReport'"` |
| `runtime` | module | `builtins` | `` |
| `runtime_fingerprint` | function | `company_ui.runtime.compatibility` | `() -> "'dict[str, str \| None]'"` |
| `runtime_smoke` | module | `builtins` | `` |
| `safe_filename` | function | `company_ui.security.redaction` | `(filename: "'str'") -> "'str'"` |
| `scan_source_contract` | function | `company_ui.certification.nicegui_runtime_contract` | `(root: "'Path \| None'" = None) -> "'tuple[RuntimeContractIssue, ...]'"` |
| `search_icons` | function | `company_ui.visual.registry` | `(query: "'str'", category: "'str \| None'" = None, domain: "'str \| None'" = None, limit: "'int'" = 30) -> "'list[IconDefinition]'"` |
| `security` | module | `builtins` | `` |
| `serialize_application_snapshot` | function | `company_ui.runtime.persistence` | `(snapshot: "'ApplicationSnapshot'", indent: "'int \| None'" = None) -> "'str'"` |
| `series_rows` | function | `company_ui.visualization.engine` | `(series: "'Sequence[Any]'") -> "'list[dict[str, Any]]'"` |
| `services` | module | `builtins` | `` |
| `set_correlation_id` | function | `company_ui.diagnostics.correlation` | `(value: "'str \| None'" = None) -> "'contextvars.Token'"` |
| `sha256_file` | function | `company_ui.supply_chain` | `(path: "'str \| Path'") -> "'str'"` |
| `spatial_bounds` | function | `company_ui.visualization.engine` | `(points: "'Sequence[SpatialPoint]'") -> "'tuple[float, float, float, float] \| None'"` |
| `stable_series_color` | function | `company_ui.visualization.palette` | `(key: "'str'", palette: "'tuple[str, ...]'" = ('#2F6FED', '#8A5CF6', '#00A17A', '#D97706', '#D14D72', '#168AAD', '#7C7C85', '#B45F06')) -> "'str'"` |
| `standard_scenarios` | function | `company_ui.certification.mac_browser` | `(include_edge: "'bool'" = True) -> "'tuple[BrowserScenario, ...]'"` |
| `state` | module | `builtins` | `` |
| `summarize_population` | function | `company_ui.engineering.analytics` | `(name: "'str'", role: "'PopulationRole'", values: "'Iterable[float]'", unit: "'str \| None'" = None) -> "'PopulationSummary'"` |
| `supply_chain` | module | `builtins` | `` |
| `uncovered_components` | function | `company_ui.certification.mac_coverage` | `(valid_routes: "'set[str] \| None'" = None) -> "'tuple[str, ...]'"` |
| `unresolved_custom_properties` | function | `company_ui.certification.visual_audit` | `(css: "'str'") -> "'tuple[str, ...]'"` |
| `uploads` | module | `builtins` | `` |
| `validate_app` | function | `company_ui.ai.validator` | `(root: "'str \| Path'", config: "'ValidatorConfig \| None'" = None) -> "'ValidationReport'"` |
| `validate_incoming_correlation_id` | function | `company_ui.diagnostics.correlation` | `(value: "'str \| None'") -> "'str \| None'"` |
| `validate_python_file` | function | `company_ui.ai.validator` | `(path: "'str \| Path'", root: "'str \| Path \| None'" = None, config: "'ValidatorConfig \| None'" = None) -> "'tuple[ValidationIssue, ...]'"` |
| `validate_svg_file` | function | `company_ui.visual.validation` | `(path: "'Path'") -> "'list[AssetValidationIssue]'"` |
| `validate_visual_package` | function | `company_ui.visual.validation` | `() -> "'list[AssetValidationIssue]'"` |
| `verify_visual_baseline` | function | `company_ui.certification.mac_baseline` | `(baseline_dir: "'Path'") -> "'tuple[bool, str]'"` |
| `version` | module | `builtins` | `` |
| `visual` | module | `builtins` | `` |
| `visual_audit` | module | `builtins` | `` |
| `visualization` | module | `builtins` | `` |
| `wafer_bounds` | function | `company_ui.visualization.engine` | `(points: "'Sequence[WaferPoint]'") -> "'tuple[float, float, float, float] \| None'"` |
| `workspace` | module | `builtins` | `` |
| `workspace_snapshot_from_dict` | function | `company_ui.runtime.persistence` | `(payload: "'Mapping[str, Any]'") -> "'WorkspaceSnapshot'"` |
| `workspace_snapshot_to_dict` | function | `company_ui.runtime.persistence` | `(snapshot: "'WorkspaceSnapshot'") -> "'dict[str, Any]'"` |
| `write_evidence` | function | `company_ui.certification.live_checks` | `(report: "'GoldCertificationReport'", path: "'str \| Path'") -> "'Path'"` |
