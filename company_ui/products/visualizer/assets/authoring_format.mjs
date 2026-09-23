// Governed presentation semantics shared by metrics, Preview, and exports.
// Stored values remain typed and unchanged; normalization is presentation-only.

const FORMATS = new Set(['auto', 'number', 'percent', 'currency', 'compact']);
const CURRENCY_CODES = new Set(['USD', 'EUR', 'GBP', 'JPY', 'CNY', 'CAD', 'AUD']);
const has = (value, key) => Object.prototype.hasOwnProperty.call(value || {}, key);
const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
const text = value => String(value ?? '');
const finite = value => typeof value === 'number' && Number.isFinite(value);
const precisionValue = value => {
  const normalized = typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : value;
  return Number.isInteger(normalized) && normalized >= 0 && normalized <= 8 ? normalized : null;
};
const CURRENCY_SYMBOLS = Object.freeze({USD:'$', EUR:'€', GBP:'£', JPY:'¥', CNY:'¥', CAD:'CA$', AUD:'A$'});

function compactConfig(value) {
  const source = object(value);
  const divisor = finite(source.divisor) && source.divisor > 0 ? source.divisor : null;
  return {divisor, unit:text(source.unit)};
}

/** Resolve current format fields, field semantics, and legacy report fields.
 * Explicit item metric_format wins; explicit bound-field metadata wins over
 * legacy presentation fields copied from an older component style.
 */
export function normalizeMetricFormat(entry = {}, field = null) {
  entry = object(entry);
  field = object(field);
  const configured = object(entry.metric_format);
  const data = object(field.format);
  const fieldUnitPresent = has(field, 'unit');
  const fieldUnit = text(field.unit);
  const currencyCode = fieldUnit.toUpperCase();
  const itemUnitPresent = has(entry, 'unit');
  const itemUnit = text(entry.unit);
  const itemCurrencyCode = itemUnit.toUpperCase();
  const explicitKind = FORMATS.has(configured.kind) ? configured.kind : null;
  const dataKind = FORMATS.has(data.kind) ? data.kind
    : FORMATS.has(field.value_format) ? field.value_format : null;
  const legacyKind = FORMATS.has(entry.value_format) ? entry.value_format : 'auto';
  let kind = explicitKind || dataKind;
  if (!kind && fieldUnitPresent) {
    if (fieldUnit === '%') kind = 'percent';
    else if (CURRENCY_SYMBOLS[currencyCode]) kind = 'currency';
    else kind = 'number';
  }
  if (!kind) kind = legacyKind;

  const precision = has(configured, 'precision')
    ? precisionValue(configured.precision)
    : has(data, 'precision') ? precisionValue(data.precision)
      : precisionValue(entry.decimals);
  const compact = has(configured, 'compact') ? compactConfig(configured.compact) : compactConfig(data.compact);
  const compactDivisor = has(configured, 'compact_divisor')
    ? (finite(configured.compact_divisor) && configured.compact_divisor > 0 ? configured.compact_divisor : null)
    : has(data, 'compact_divisor') ? (finite(data.compact_divisor) && data.compact_divisor > 0 ? data.compact_divisor : null)
      : compact.divisor;
  const compactUnit = has(configured, 'compact_unit') ? text(configured.compact_unit)
    : has(data, 'compact_unit') ? text(data.compact_unit) : compact.unit;

  let prefix;
  if (has(configured, 'prefix')) prefix = text(configured.prefix);
  else if (has(data, 'prefix')) prefix = text(data.prefix);
  else if (kind === 'currency') prefix = CURRENCY_SYMBOLS[currencyCode] || CURRENCY_SYMBOLS[itemCurrencyCode] || text(entry.currency_symbol) || '$';
  else prefix = '';

  let suffix;
  if (has(configured, 'suffix')) suffix = text(configured.suffix);
  else if (has(data, 'suffix')) suffix = text(data.suffix);
  else if (kind === 'percent') suffix = '%';
  else if (compactUnit) suffix = compactUnit;
  else if (fieldUnitPresent) suffix = CURRENCY_SYMBOLS[currencyCode] && kind === 'currency' ? '' : fieldUnit;
  else if (legacyKind === 'percent') suffix = '%';
  else if (itemUnitPresent) suffix = CURRENCY_SYMBOLS[itemCurrencyCode] && kind === 'currency' ? '' : itemUnit;
  else if (legacyKind === 'currency') suffix = '';
  else suffix = text(entry.unit);

  const percentScale = ['ratio', 'points'].includes(configured.percent_scale) ? configured.percent_scale
    : ['ratio', 'points'].includes(data.percent_scale) ? data.percent_scale
      : data.scale === 'ratio' ? 'ratio' : 'points';
  const signDisplay = ['auto', 'always', 'exceptZero', 'never'].includes(configured.signDisplay)
    ? configured.signDisplay : ['auto', 'always', 'exceptZero', 'never'].includes(data.signDisplay) ? data.signDisplay : 'auto';
  const nullDisplay = has(configured, 'null_display') ? text(configured.null_display)
    : has(data, 'null_display') ? text(data.null_display) : '—';

  // A data unit already names the scale. Applying compact notation on top of
  // that unit would silently turn e.g. 48.2 M into 48.2M M.
  if (fieldUnitPresent && fieldUnit && !dataKind && !explicitKind && kind === 'compact' && !compactDivisor) kind = 'number';

  return {
    kind, precision, prefix, suffix, percentScale, signDisplay, nullDisplay,
    compactDivisor, compactUnit,
    suffixSeparator: has(configured, 'suffix_separator') ? text(configured.suffix_separator)
      : has(data, 'suffix_separator') ? text(data.suffix_separator) : null,
  };
}

function formatNumber(value, {precision = null, signDisplay = 'auto', grouping = true} = {}) {
  const negative = value < 0 || Object.is(value, -0);
  const magnitude = Math.abs(value);
  const minimum = precision === null ? 0 : precision;
  const maximum = precision === null ? 20 : precision;
  const body = new Intl.NumberFormat('en-US', {
    useGrouping:grouping,
    minimumFractionDigits:minimum,
    maximumFractionDigits:maximum,
  }).format(magnitude);
  const sign = signDisplay === 'never' ? '' : negative ? '-' : (signDisplay === 'always' || (signDisplay === 'exceptZero' && magnitude !== 0)) ? '+' : '';
  return {body, sign};
}

/** Format the numeric portion; compatible with the previous helper API. */
export function formatMetricDisplay(value, options = {}) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value !== 'number' || !Number.isFinite(value)) return String(value);
  const source = object(options);
  const style = FORMATS.has(source.style) ? source.style : FORMATS.has(source.kind) ? source.kind : 'auto';
  const precision = has(source, 'precision') ? precisionValue(source.precision)
    : has(source, 'decimals') ? precisionValue(source.decimals) : null;
  const signDisplay = ['auto', 'always', 'exceptZero', 'never'].includes(source.signDisplay) ? source.signDisplay : 'auto';
  let number = value;
  let suffix = text(source.compact_unit);
  if (finite(source.compact_divisor) && source.compact_divisor > 0) number /= source.compact_divisor;

  let formatted;
  if (style === 'compact' && !suffix && !(finite(source.compact_divisor) && source.compact_divisor > 0)) {
    const negative = number < 0 || Object.is(number, -0), zero = number === 0;
    const sign = signDisplay === 'never' ? '' : negative ? '-' : (signDisplay === 'always' || (signDisplay === 'exceptZero' && !zero)) ? '+' : '';
    formatted = new Intl.NumberFormat('en-US', {
      notation:'compact', maximumFractionDigits:precision ?? 1, minimumFractionDigits:precision ?? 0,
    }).format(Math.abs(number));
    return `${sign}${formatted}`;
  }

  const {body, sign} = formatNumber(number, {precision, signDisplay, grouping:style !== 'auto' || precision !== null});
  const prefix = style === 'currency' ? text(source.prefix ?? source.currency ?? '$') : text(source.prefix);
  formatted = `${sign}${prefix}${body}`;
  return formatted;
}

export function metricDisplayUnit(entry = {}, field = null) {
  return normalizeMetricFormat(entry, field).suffix;
}

function numericOptions(format) {
  return {
    style:format.kind,
    precision:format.precision,
    prefix:format.prefix,
    percent_scale:format.percentScale,
    compact_divisor:format.compactDivisor,
    compact_unit:format.compactUnit,
    signDisplay:format.signDisplay,
  };
}

/** Format a metric with its normalized prefix, suffix, and null semantics. */
export function formatMetricValue(value, entry = {}, field = null) {
  const format = normalizeMetricFormat(entry, field);
  if (value === null || value === undefined || value === '') return format.nullDisplay;
  const scaled = format.kind === 'percent' && format.percentScale === 'ratio' && finite(value) ? value * 100 : value;
  const numeric = formatMetricDisplay(scaled, numericOptions(format));
  if (numeric === null) return format.nullDisplay;
  const suffix = format.suffix;
  if (!suffix) return numeric;
  const separator = format.suffixSeparator !== null ? format.suffixSeparator : (/^[%‰°]/u.test(suffix) ? '' : ' ');
  return `${numeric}${separator}${suffix}`;
}

/** Material formatting contradictions block export; presentation-only differences do not. */
export function metricFormattingIssues(entry = {}, field = null) {
  const issues = [];
  const format = normalizeMetricFormat(entry, field);
  const data = object(object(field).format);
  const metricFormat = object(object(entry).metric_format);
  const fieldUnit = text(object(field).unit);
  const hasExplicitItemFormat = Object.keys(metricFormat).length > 0;
  const semanticKind = FORMATS.has(data.kind) ? data.kind
    : FORMATS.has(object(field).value_format) ? field.value_format
      : Object.prototype.hasOwnProperty.call(object(field), 'unit') && (fieldUnit !== '' || !hasExplicitItemFormat)
        ? fieldUnit === '%' ? 'percent' : CURRENCY_CODES.has(fieldUnit.toUpperCase()) ? 'currency' : 'number'
        : null;
  const legacyKind = FORMATS.has(object(entry).value_format) ? entry.value_format : null;
  const presentationKind = FORMATS.has(metricFormat.kind) ? metricFormat.kind : legacyKind;
  if (semanticKind && presentationKind && presentationKind !== semanticKind) {
    issues.push(`${semanticKind[0].toUpperCase()}${semanticKind.slice(1)} data is paired with ${presentationKind} formatting. Set a matching metric format before export.`);
  }
  if (semanticKind === 'percent' && legacyKind === 'currency' && !hasExplicitItemFormat && !issues.some(issue => issue.includes('currency formatting'))) {
    issues.push('Percent data is paired with legacy currency formatting. Set the metric format to Percent before export.');
  }
  if (semanticKind === 'percent' && format.prefix && /[$€£¥]/u.test(format.prefix)) {
    issues.push('Percent semantics cannot use a currency prefix.');
  }
  const configuredUnit = metricFormat.compact_unit ?? object(metricFormat.compact).unit ?? data.compact_unit ?? object(data.compact).unit;
  if (configuredUnit && !format.suffix.includes(String(configuredUnit))) {
    issues.push(`Configured compact unit “${configuredUnit}” is missing from the rendered value.`);
  }
  return issues;
}

export function prepareChartRows(rawRows, {
  sortMode='input',
  missingPolicy='gap',
}={}) {
  let rows=(rawRows||[]).map((row,index)=>({
    ...row,
    __index:index,
    value:(missingPolicy==='zero' && (row?.value===null||row?.value===undefined||row?.value===''))
      ? 0
      : row?.value,
  }));

  if(missingPolicy==='drop') {
    rows=rows.filter(row=>row.value!==null&&row.value!==undefined&&row.value!=='');
  }

  const numeric=row=>typeof row.value==='number'&&Number.isFinite(row.value);

  if(sortMode==='value-asc' || sortMode==='value-desc') {
    const direction=sortMode==='value-asc'?1:-1;
    rows.sort((a,b)=>{
      const an=numeric(a),bn=numeric(b);
      if(an&&bn) return (a.value-b.value)*direction || a.__index-b.__index;
      if(an!==bn) return an?-1:1;
      return a.__index-b.__index;
    });
  } else if(sortMode==='label-asc') {
    rows.sort((a,b)=>String(a.label??'').localeCompare(String(b.label??''),undefined,{numeric:true})||a.__index-b.__index);
  }

  return rows.map(({__index,...row})=>row);
}
