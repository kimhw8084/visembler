# Visembler authoring productivity matrix

This is the maintained product-engineering matrix for the 52 production
elements. It records the shared authoring contract rather than pretending that
each element needs a bespoke editor.

Abbreviations: `DF` = Data First intake/Data Dock, `DE` = direct edit, `S` =
shared selection/arrange/undo system, `I` = Inspector, `CS` = Chart Studio,
`DS` = Diagram Studio, `fit` = Smart/Guided content-fit sizing, and `KB` =
keyboard movement/clipboard/undo support. “Baseline” means the current golden
behavior was audited and retained; “wave” means it receives the shared typed
clipboard/direct-edit improvement in this wave.

| Element | Purpose | Create UX | Data UX | Edit UX | Manipulation UX | Style / output | Responsive / KB | Status | Primary friction / next improvement | Shared primitive | Priority | Tests |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Hero Title | Report headline | Library or intake headline suggestion | Text intake | DE/I | S + inline title | Strong hierarchy, wrap | fit + KB | Baseline | Choosing a role is still optional | text intake, roles | P1 | element fixtures, data-first |
| Section Heading | Section structure | Library | Text intake | DE/I | S | Hierarchy | fit + KB | Baseline | No section-level batch authoring | text intake, roles | P1 | element fixtures |
| Executive Statement | Executive conclusion | Library or text recommendation | Text intake | DE/I | S | Emphasis/status | fit + KB | Baseline | Longer content needs review | text intake, roles | P1 | element fixtures |
| Body Narrative | Supporting explanation | Library or text recommendation | Text intake | DE/I | S | Wrap and readable density | fit + KB | Baseline | Long narrative still benefits from manual review | text intake, typed text | P1 | element fixtures |
| Key Takeaway | Concise insight | Library or text recommendation | Text intake | DE/I | S | Highlighted callout | fit + KB | Baseline | No deterministic insight extraction | text intake, roles | P1 | element fixtures |
| Hero KPI | Headline measure | Library or metric intake | DF / typed scalar | DE value/I variant | S | Numeric hierarchy | fit + KB | Baseline | Source selection is still a decision | typed data, metric inspector | P0 | metric parity, fixtures |
| Metric + Delta | Period comparison | Library or metric intake | DF / typed scalar | DE value/I | S | Delta and period context | fit + KB | Baseline | Comparison source is manual | typed data, metric inspector | P0 | metric parity |
| Target vs Actual | Goal comparison | Library or metric intake | DF / typed scalar | I semantic fields | S | Variance readable | fit + KB | Baseline | Target mapping needs review | typed data, semantic inspector | P0 | metric parity |
| Progress Metric | Bounded progress | Library or metric intake | DF / typed scalar | I semantic fields | S | Progress scale | fit + KB | Baseline | Max is user-supplied | typed data, metric inspector | P0 | metric parity |
| Status Metric | State plus value | Library or metric intake | DF / typed scalar | DE/I status/detail | S | Status semantics | fit + KB | Baseline | Status vocabulary is free text | typed data, semantic inspector | P1 | metric parity |
| Capacity Metric | Usage/capacity | Library or metric intake | DF / typed scalar | I semantic fields | S | Capacity relation | fit + KB | Baseline | Capacity role selection | typed data, metric inspector | P1 | metric parity |
| Rate Metric | Numerator/denominator | Library or metric intake | DF / typed scalar | I semantic fields | S | Unit/period | fit + KB | Baseline | Rate basis can be unclear | typed data, metric inspector | P1 | metric parity |
| Threshold Metric | Warning/critical value | Library or metric intake | DF / typed scalar | I thresholds | S | Directional status | fit + KB | Baseline | Threshold policy is manual | typed data, semantic inspector | P1 | metric parity |
| Metric with Sparkline | KPI plus trend | Library or trend intake | DF / series | I series + DE value | S | Compact trend | fit + KB | Baseline | Series setup is still manual | typed data, chart data | P1 | metric parity |
| Metric Ring | Bounded visual KPI | Library or metric intake | DF / typed scalar | I value/max | S | Explicit max, readable export | fit + KB | Baseline | Best for bounded measures only | typed data, metric inspector | P1 | metric parity |
| As-Is → To-Be | State transition | Library or text/metric | DF / typed scalar | I before/after | S | Unit-aware comparison | fit + KB | Baseline | Labels are fixed variant semantics | typed data, comparison inspector | P1 | comparison tests |
| Before/After KPI | KPI comparison | Library or metric intake | DF / typed scalar | I before/after | S | Unit-aware comparison | fit + KB | Baseline | Reuse across reports can improve | typed data, comparison inspector | P1 | comparison tests |
| Time Compression | Cycle-time change | Library or metric intake | DF / typed scalar | I before/after | S | Time/unit semantics | fit + KB | Baseline | Unit must be supplied | typed data, comparison inspector | P1 | comparison tests |
| Vertical Bar | Category comparison | Data First recommendation | DF / mapping | CS for advanced, I for data | S + fit | Static labels/values | fit + KB | Baseline | Advanced styling belongs in CS | DF, typed grid, chart adapter | P0 | data-first, chart acceptance |
| Horizontal Bar | Long-label ranking | Data First recommendation | DF / mapping | CS/I | S + fit | Labels remain usable | fit + KB | Baseline | Recommendation depends on label shape | DF, chart adapter | P0 | chart acceptance |
| Line Chart | Ordered trend | Data First recommendation | DF / mapping | CS/I | S + fit | Axes/legend static-readable | fit + KB | Baseline | Mapping should remain one-click | DF, chart adapter | P0 | chart acceptance |
| Area Chart | Trend with magnitude | Data First alternative | DF / mapping | CS/I | S + fit | Area opacity/labels | fit + KB | Baseline | Alternative selection is explicit | DF, chart adapter | P0 | chart acceptance |
| Multi-Line | Compare multiple ordered runs | Data First recommendation | DF / x-y-series mapping | CS/I | S + fit | Legend and series semantics | fit + KB | Promoted | Multiple runs remain comparable without repasting | DF, chart adapter | P0 | analytics wave, chart acceptance |
| Scatter Plot | Relationship between measures | Data First recommendation | DF / numeric x-y mapping | CS/I | S + fit | Numeric axes and point tooltips | fit + KB | Promoted | Outlier interpretation remains engineer-led | DF, chart adapter | P0 | analytics wave, chart acceptance |
| Regression Scatter | Relationship plus fitted trend | Data First recommendation | DF / numeric x-y mapping | CS/I | S + fit | Fit and R² are explicit | fit + KB | Promoted | Statistical inference remains descriptive | DF, advanced chart adapter | P0 | analytics wave, chart acceptance |
| Histogram | Single-measure distribution | Data First recommendation | DF / numeric value mapping | CS/I | S + fit | Bins and counts are readable | fit + KB | Promoted | Bin policy is deterministic and inspectable | DF, advanced chart adapter | P0 | analytics wave, chart acceptance |
| Box Plot | Spread, median, outliers | Data First alternative | DF / numeric value mapping | CS/I | S + fit | Quartiles and outliers are explicit | fit + KB | Promoted | One distribution at a time in this wave | DF, advanced chart adapter | P0 | analytics wave, chart acceptance |
| Pareto | Prioritize categorical contribution | Data First recommendation | DF / category-value mapping | CS/I | S + fit | Descending impact plus cumulative share | fit + KB | Promoted | Source must represent a meaningful contribution | DF, chart adapter | P0 | analytics wave, chart acceptance |
| Clean Table | Engineering data grid | Data First default | Rectangular paste, DF | Grid DE/I | S + range actions | Typed values, readable density | virtualized + KB | wave | Direct cell edits must preserve field type; fixed in shared parser | typed grid, clipboard | P0 | typed scalar regression, grid tests |
| Event Timeline | Events over time | Data First recommendation | DF / timeline mapping | DE milestone/I | S + fit | Dates/labels | fit + KB | Baseline | Long event lists need compact review | DF, timeline renderer | P1 | timeline fixtures |
| Milestone Rail | Compact milestones | Library / timeline intake | DF / timeline mapping | DE/I | S | Rail semantics | fit + KB | Baseline | Needs data-driven spacing | DF, timeline renderer | P1 | timeline fixtures |
| Sequence Strip | Ordered sequence | Library / process intake | DF / timeline mapping | DE/I | S | Sequence readability | fit + KB | Baseline | Simple sequences should stay simple | DF, timeline renderer | P1 | timeline fixtures |
| Process Flow | Process nodes/connectors | Process-step intake or DS | DF / DS structured model | DE nodes, DS advanced | S / DS | Static graph | fit + KB | Baseline | Advanced edits belong in DS | DF, DS adapter | P1 | diagram acceptance |
| Data Flow | Source-target graph | Source/target intake or DS | DF / DS structured model | DE nodes, DS advanced | S / DS | Direction/labels | fit + KB | Baseline | Mapping validation is important | DF, DS adapter | P1 | diagram acceptance |
| Image | Technical image | Paste/drop/library | Image clipboard/file | DE/I alt/fit | S | Fit/fill, alt semantics | fit + KB | Baseline | Crop/annotation remain bounded features | image clipboard, media inspector | P0 | image tests |
| Image + Caption | Image evidence | Paste/drop suggestion | Image plus caption/alt | DE caption/I | S | Caption/readability | fit + KB | Baseline | Caption prompt can be more direct | image clipboard, DE | P0 | image tests |
| Screenshot Frame | App evidence | Paste/drop/library | Image clipboard/file | DE caption/I | S | Frame presentation | fit + KB | Baseline | Source metadata is manual | image clipboard, media inspector | P1 | image tests |
| Evidence Card | Evidence statement | Library / text intake | DF only when linked | I/DE text | S | Statement/detail/status | fit + KB | Baseline | Evidence hierarchy can be suggested | text intake, roles | P1 | composite tests |
| Risk Callout | Risk/action | Library / text intake | DF only when linked | I/DE text | S | Status semantics | fit + KB | Baseline | Action capture remains manual | text intake, roles | P1 | composite tests |
| Project Card | Project summary | Library / text intake | DF only when linked | I/DE statement/detail/status | S | Truthful modeled status | fit + KB | Baseline | No fabricated owner/progress | text intake, roles | P1 | project tests |
| SPC Control Chart | Process control | Engineering Data First | DF observations/spec roles | I/CS engineering | S + fit | Spec/control distinction | fit + KB | Baseline | Advanced statistics stay explicit | DF, chart adapter | P0 | engineering tests |
| I-MR Chart | Individuals/moving range | Engineering Data First | DF observations | I/CS engineering | S + fit | I/MR labeling | fit + KB | Baseline | Variant choice requires understanding | DF, chart adapter | P0 | engineering tests |
| CUSUM Chart | Sustained shifts | Engineering Data First | DF observations/params | I/CS engineering | S + fit | Parameters visible | fit + KB | Baseline | Parameter defaults need context | DF, chart adapter | P0 | engineering tests |
| EWMA Chart | Small shifts | Engineering Data First | DF observations/params | I/CS engineering | S + fit | Parameters visible | fit + KB | Baseline | Parameter defaults need context | DF, chart adapter | P0 | engineering tests |
| Xbar-R Chart | Constant-size subgroup means/ranges | Statistical Data First | DF subgroup/measurement/order | I/CS statistical | S + fit | X̄/R panels, explicit control limits | fit + KB | Promoted | Signals describe unusual behavior, not root cause | DF, statistics backend | P0 | statistical quality wave |
| DOE Main Effects | Observed response means by factor level | Statistical Data First | DF factor/response mapping | I/CS statistical | S + fit | Descriptive means, no significance claim | fit + KB | Promoted | Factor-level ordering remains deterministic | DF, statistics backend | P0 | statistical quality wave |
| DOE Interaction Plot | Observed response means by factor cell | Statistical Data First | DF factor A/factor B/response | I/CS statistical | S + fit | Shared scale, missing-cell validation | fit + KB | Promoted | Descriptive interaction only | DF, statistics backend | P0 | statistical quality wave |
| Wafer Map | Spatial wafer evidence | Wafer Data First | DF coordinates/value/identity | I/Chart Studio | S + fit | Outline, legend, identity | fit + KB | Baseline | Filtering/selection is specialized | DF, wafer adapter | P0 | wafer/chart acceptance |
| Wafer Difference Map | Signed affected-minus-reference die comparison | Data First recommendation | DF coordinates/reference/affected mapping | I/Chart Studio | S + fit | Zero-centered delta, source-value tooltip | fit + KB | Promoted | Duplicate die policy and missing pairs remain explicit | DF, wafer adapter | P0 | fab semantic fixtures |
| Tool × Chamber Matrix | Equipment/module measurement comparison | Data First recommendation | DF tool/chamber/value mapping | I/Chart Studio | S + fit | Shared scale, aggregation, missing cells | fit + KB | Promoted | Matrix selection requires compound filters when bound | DF, wafer adapter | P0 | fab semantic fixtures |
| Golden vs Affected Profile | Reference versus affected process profile | Data First recommendation | DF ordered-X/reference-affected or cohort-value mapping | I/Chart Studio | S + fit | Shared domain, explicit legend, no interpolation | fit + KB | Promoted | Missing positions remain gaps | DF, wafer adapter | P0 | fab semantic fixtures |
| Control vs Affected Distribution | Observed cohort distribution comparison | Data First recommendation | DF cohort/value mapping | I/Chart Studio | S + fit | Shared scale, counts, observed box summaries | fit + KB | Promoted | No significance/capability claim without a statistic | DF, wafer adapter | P0 | fab semantic fixtures |

## Wave result

## Scoring

The matrix uses a deliberately conservative five-point usability score rather
than a fabricated benchmark: every `Baseline` row is **4/5** (usable and
covered by the golden regression gates, with the limitation stated in its
row), while the `wave` Clean Table row is **4.5/5** because its direct-edit
path now preserves field typing as well as the existing interaction contract.
No element is scored 5/5 without an observed task benchmark for that specific
workflow.

The audited high-frequency shared improvement is the field-aware typed-cell
parser. It applies to Clean Table and every dataset-backed visual that exposes
inline cell editing; it keeps numeric `0`, string `"0"`, `""`, and null/missing
distinct. Clipboard intake now uses the same content-first route from the
toolbar and blank-canvas paste action, while normal focused controls retain
browser paste behavior.

The remaining limitations are intentional: advanced chart configuration stays
in Chart Studio, advanced graph manipulation stays in Diagram Studio, and
free-form image annotation/cropping is not expanded in this wave.
