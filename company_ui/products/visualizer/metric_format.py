"""Canonical metric presentation semantics used by supported exports.

The browser counterpart is ``assets/authoring_format.mjs``. Both consume the
same persisted ``metric_format`` contract; parity fixtures live in the focused
CHG-179 tests. Values in the report model are never changed by this module.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
from typing import Any, Mapping

FORMATS = frozenset({'auto', 'number', 'percent', 'currency', 'compact'})
_CURRENCY_SYMBOLS = {'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CNY': '¥', 'CAD': 'CA$', 'AUD': 'A$'}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _precision(value: Any) -> int | None:
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 8 else None


def normalize_metric_format(entry: Mapping[str, Any] | None = None, field: Mapping[str, Any] | None = None) -> dict[str, Any]:
    entry, field = _mapping(entry), _mapping(field)
    configured, data = _mapping(entry.get('metric_format')), _mapping(field.get('format'))
    field_unit_present = 'unit' in field
    field_unit = str(field.get('unit') or '')
    currency_code = field_unit.upper()
    item_unit_present = 'unit' in entry
    item_unit = str(entry.get('unit') or '')
    item_currency_code = item_unit.upper()
    explicit_kind = configured.get('kind') if configured.get('kind') in FORMATS else None
    data_kind = data.get('kind') if data.get('kind') in FORMATS else field.get('value_format') if field.get('value_format') in FORMATS else None
    legacy_kind = entry.get('value_format') if entry.get('value_format') in FORMATS else 'auto'
    kind = explicit_kind or data_kind
    if not kind and field_unit_present:
        kind = 'percent' if field_unit == '%' else 'currency' if currency_code in _CURRENCY_SYMBOLS else 'number'
    kind = kind or legacy_kind

    precision = _precision(configured.get('precision')) if 'precision' in configured else _precision(data.get('precision')) if 'precision' in data else _precision(entry.get('decimals'))
    compact = _mapping(configured.get('compact')) if 'compact' in configured else _mapping(data.get('compact'))
    compact_divisor = configured.get('compact_divisor') if 'compact_divisor' in configured else data.get('compact_divisor') if 'compact_divisor' in data else compact.get('divisor')
    if not isinstance(compact_divisor, (int, float)) or isinstance(compact_divisor, bool) or not math.isfinite(compact_divisor) or compact_divisor <= 0:
        compact_divisor = None
    compact_unit = str(configured.get('compact_unit') or '') if 'compact_unit' in configured else str(data.get('compact_unit') or compact.get('unit') or '')

    if 'prefix' in configured:
        prefix = str(configured.get('prefix') or '')
    elif 'prefix' in data:
        prefix = str(data.get('prefix') or '')
    elif kind == 'currency':
        prefix = _CURRENCY_SYMBOLS.get(currency_code) or _CURRENCY_SYMBOLS.get(item_currency_code) or str(entry.get('currency_symbol') or '$')
    else:
        prefix = ''

    if 'suffix' in configured:
        suffix = str(configured.get('suffix') or '')
    elif 'suffix' in data:
        suffix = str(data.get('suffix') or '')
    elif kind == 'percent':
        suffix = '%'
    elif compact_unit:
        suffix = compact_unit
    elif field_unit_present:
        suffix = '' if currency_code in _CURRENCY_SYMBOLS and kind == 'currency' else field_unit
    elif legacy_kind == 'percent':
        suffix = '%'
    elif item_unit_present:
        suffix = '' if item_currency_code in _CURRENCY_SYMBOLS and kind == 'currency' else item_unit
    elif legacy_kind == 'currency':
        suffix = ''
    else:
        suffix = str(entry.get('unit') or '')

    percent_scale = configured.get('percent_scale') if configured.get('percent_scale') in {'ratio', 'points'} else data.get('percent_scale') if data.get('percent_scale') in {'ratio', 'points'} else 'ratio' if data.get('scale') == 'ratio' else 'points'
    sign_display = configured.get('signDisplay') if configured.get('signDisplay') in {'auto', 'always', 'exceptZero', 'never'} else data.get('signDisplay') if data.get('signDisplay') in {'auto', 'always', 'exceptZero', 'never'} else 'auto'
    null_display = str(configured.get('null_display')) if 'null_display' in configured else str(data.get('null_display')) if 'null_display' in data else '—'
    separator = str(configured.get('suffix_separator')) if 'suffix_separator' in configured else str(data.get('suffix_separator')) if 'suffix_separator' in data else None

    if field_unit_present and field_unit and not data_kind and not explicit_kind and kind == 'compact' and not compact_divisor:
        kind = 'number'
    return {
        'kind': kind, 'precision': precision, 'prefix': prefix, 'suffix': suffix,
        'percent_scale': percent_scale, 'signDisplay': sign_display, 'null_display': null_display,
        'compact_divisor': compact_divisor, 'compact_unit': compact_unit, 'suffix_separator': separator,
    }


def _grouped_number(value: Any, precision: int | None, sign_display: str, *, group: bool = True) -> str:
    number = Decimal(str(value))
    negative = number.is_signed()
    magnitude = abs(number)
    if precision is not None:
        magnitude = magnitude.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
        rendered = f'{magnitude:,.{precision}f}' if group else f'{magnitude:.{precision}f}'
    else:
        rendered = format(magnitude, 'f')
        if '.' in rendered:
            rendered = rendered.rstrip('0').rstrip('.')
        if group:
            whole, dot, fraction = rendered.partition('.')
            rendered = f'{int(whole):,}' + (dot + fraction if dot else '')
    zero = magnitude == 0
    sign = '' if sign_display == 'never' else '-' if negative else '+' if sign_display == 'always' or (sign_display == 'exceptZero' and not zero) else ''
    return sign + rendered


def _formatted_number(value: Any, fmt: Mapping[str, Any]) -> str:
    style = fmt['kind']
    number = value
    if fmt['percent_scale'] == 'ratio' and style == 'percent':
        number = Decimal(str(number)) * Decimal(100)
    if fmt['compact_divisor']:
        number = Decimal(str(number)) / Decimal(str(fmt['compact_divisor']))
    if style == 'compact' and not fmt['compact_unit'] and not fmt['compact_divisor']:
        magnitude = abs(Decimal(str(number)))
        for divisor, unit in ((Decimal('1e12'), 'T'), (Decimal('1e9'), 'B'), (Decimal('1e6'), 'M'), (Decimal('1e3'), 'K')):
            if magnitude >= divisor:
                number = Decimal(str(number)) / divisor
                body = _grouped_number(number, fmt['precision'] if fmt['precision'] is not None else 1, fmt['signDisplay'], group=False)
                if fmt['precision'] is None and '.' in body:
                    body = body.rstrip('0').rstrip('.')
                return f'{body}{unit}'
    prefix = fmt['prefix'] if style == 'currency' or fmt['prefix'] else ''
    number_text = _grouped_number(number, fmt['precision'], fmt['signDisplay'], group=style != 'auto' or fmt['precision'] is not None)
    if number_text.startswith(('-', '+')):
        return f'{number_text[0]}{prefix}{number_text[1:]}'
    return f'{prefix}{number_text}'


def format_metric_value(value: Any, entry: Mapping[str, Any] | None = None, field: Mapping[str, Any] | None = None) -> str:
    fmt = normalize_metric_format(entry, field)
    if value is None or value == '':
        return fmt['null_display']
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return str(value)
    try:
        if not math.isfinite(float(value)):
            return str(value)
        rendered = _formatted_number(value, fmt)
    except (InvalidOperation, ValueError, OverflowError):
        return str(value)
    suffix = fmt['suffix']
    if not suffix:
        return rendered
    separator = fmt['suffix_separator'] if fmt['suffix_separator'] is not None else '' if suffix[:1] in {'%', '‰', '°'} else ' '
    return f'{rendered}{separator}{suffix}'


def metric_format_issues(entry: Mapping[str, Any] | None = None, field: Mapping[str, Any] | None = None) -> list[str]:
    entry, field = _mapping(entry), _mapping(field)
    fmt = normalize_metric_format(entry, field)
    data = _mapping(field.get('format'))
    metric_format = _mapping(entry.get('metric_format'))
    semantic_kind = data.get('kind') if data.get('kind') in FORMATS else field.get('value_format') if field.get('value_format') in FORMATS else None
    if semantic_kind is None and 'unit' in field:
        unit = str(field.get('unit') or '')
        if unit or not metric_format:
            semantic_kind = 'percent' if unit == '%' else 'currency' if unit.upper() in _CURRENCY_SYMBOLS else 'number'
    legacy_kind = entry.get('value_format') if entry.get('value_format') in FORMATS else None
    issues = []
    presentation_kind = metric_format.get('kind') if metric_format.get('kind') in FORMATS else legacy_kind
    if semantic_kind and presentation_kind and semantic_kind != presentation_kind:
        issues.append(f'{semantic_kind[0].upper()}{semantic_kind[1:]} data is paired with {presentation_kind} formatting. Set a matching metric format before export.')
    if semantic_kind == 'percent' and legacy_kind == 'currency' and not metric_format and not any('currency formatting' in issue for issue in issues):
        issues.append('Percent data is paired with legacy currency formatting. Set the metric format to Percent before export.')
    if semantic_kind == 'percent' and fmt['prefix'] and any(symbol in fmt['prefix'] for symbol in '$€£¥'):
        issues.append('Percent semantics cannot use a currency prefix.')
    configured_unit = metric_format.get('compact_unit') or _mapping(metric_format.get('compact')).get('unit') or data.get('compact_unit') or _mapping(data.get('compact')).get('unit')
    if configured_unit and str(configured_unit) not in fmt['suffix']:
        issues.append(f'Configured compact unit “{configured_unit}” is missing from the rendered value.')
    return issues


__all__ = ['format_metric_value', 'metric_format_issues', 'normalize_metric_format']
