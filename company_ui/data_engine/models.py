from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FilterOperation(str, Enum):
    EQUALS='equals'; NOT_EQUALS='not_equals'; IN='in'; NOT_IN='not_in'
    GT='gt'; GTE='gte'; LT='lt'; LTE='lte'; BETWEEN='between'
    CONTAINS='contains'; STARTS_WITH='starts_with'; ENDS_WITH='ends_with'
    IS_EMPTY='is_empty'; IS_NOT_EMPTY='is_not_empty'


class Aggregation(str, Enum):
    SUM='sum'; AVG='avg'; MIN='min'; MAX='max'; COUNT='count'; COUNT_DISTINCT='count_distinct'


@dataclass(frozen=True, slots=True)
class Dimension:
    key: str
    label: str | None = None
    field: str | None = None

    def __post_init__(self) -> None:
        if not self.key.strip(): raise ValueError('Dimension key must not be empty')

    @property
    def source_field(self) -> str: return self.field or self.key


@dataclass(frozen=True, slots=True)
class Metric:
    key: str
    label: str | None = None
    field: str | None = None
    aggregation: Aggregation = Aggregation.SUM

    def __post_init__(self) -> None:
        if not self.key.strip(): raise ValueError('Metric key must not be empty')
        if self.aggregation is not Aggregation.COUNT and not (self.field or self.key):
            raise ValueError('Metric field is required')

    @property
    def source_field(self) -> str | None: return self.field or (None if self.aggregation is Aggregation.COUNT else self.key)


@dataclass(frozen=True, slots=True)
class FilterClause:
    field: str
    operation: FilterOperation
    value: Any = None
    value2: Any = None
    filter_id: str | None = None

    def __post_init__(self) -> None:
        if not self.field.strip(): raise ValueError('FilterClause field must not be empty')

    @property
    def key(self) -> str: return self.filter_id or self.field


@dataclass(frozen=True, slots=True)
class SortClause:
    key: str
    descending: bool = False

    def __post_init__(self) -> None:
        if not self.key.strip(): raise ValueError('SortClause key must not be empty')


@dataclass(frozen=True, slots=True)
class DataQuery:
    filters: tuple[FilterClause, ...] = ()
    search: str = ''
    search_fields: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    sorts: tuple[SortClause, ...] = ()
    offset: int = 0
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.offset < 0: raise ValueError('offset must be >= 0')
        if self.limit is not None and self.limit < 1: raise ValueError('limit must be >= 1')


@dataclass(frozen=True, slots=True)
class DataResult:
    rows: tuple[dict[str, Any], ...]
    total: int
    revision: int = 0
    filtered_total: int | None = None


@dataclass(frozen=True, slots=True)
class DataSessionSnapshot:
    revision: int
    filters: tuple[FilterClause, ...]
    search: str = ''
