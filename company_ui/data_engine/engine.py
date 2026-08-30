from __future__ import annotations

import math
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from typing import Any, Generic, TypeVar

from .models import Aggregation, DataQuery, DataResult, DataSessionSnapshot, Dimension, FilterClause, FilterOperation, Metric, SortClause

T=TypeVar('T')
SessionWatcher=Callable[['DataSession'], Any]
BindingWatcher=Callable[['DataBinding[Any]'], Any]


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping): return tuple(sorted((str(k),_freeze(v)) for k,v in value.items()))
    if isinstance(value, (list,tuple,set,frozenset)): return tuple(_freeze(v) for v in value)
    try: hash(value); return value
    except TypeError: return repr(value)


def _numeric(value: Any) -> float | None:
    if isinstance(value,bool) or not isinstance(value,(int,float)): return None
    result=float(value)
    return result if math.isfinite(result) else None


def _matches(value: Any, clause: FilterClause) -> bool:
    op=clause.operation; target=clause.value
    if op is FilterOperation.IS_EMPTY: return value is None or value == ''
    if op is FilterOperation.IS_NOT_EMPTY: return value is not None and value != ''
    if op is FilterOperation.EQUALS: return value == target
    if op is FilterOperation.NOT_EQUALS: return value != target
    if op is FilterOperation.IN:
        try: return value in target
        except TypeError: return False
    if op is FilterOperation.NOT_IN:
        try: return value not in target
        except TypeError: return True
    if op is FilterOperation.BETWEEN:
        try: return target <= value <= clause.value2
        except TypeError: return False
    if op in {FilterOperation.GT,FilterOperation.GTE,FilterOperation.LT,FilterOperation.LTE}:
        try:
            return {FilterOperation.GT:value>target,FilterOperation.GTE:value>=target,FilterOperation.LT:value<target,FilterOperation.LTE:value<=target}[op]
        except TypeError: return False
    text='' if value is None else str(value); needle='' if target is None else str(target)
    text=text.casefold(); needle=needle.casefold()
    if op is FilterOperation.CONTAINS: return needle in text
    if op is FilterOperation.STARTS_WITH: return text.startswith(needle)
    if op is FilterOperation.ENDS_WITH: return text.endswith(needle)
    return True


def _aggregate(metric: Metric, rows: Sequence[Mapping[str,Any]]) -> Any:
    if metric.aggregation is Aggregation.COUNT:
        if metric.source_field is None: return len(rows)
        return sum(row.get(metric.source_field) is not None for row in rows)
    values=[row.get(metric.source_field) for row in rows]
    if metric.aggregation is Aggregation.COUNT_DISTINCT:
        return len({_freeze(value) for value in values if value is not None})
    numeric=[value for raw in values if (value:=_numeric(raw)) is not None]
    if metric.aggregation is Aggregation.SUM: return sum(numeric)
    if not numeric: return None
    if metric.aggregation is Aggregation.AVG: return sum(numeric)/len(numeric)
    if metric.aggregation is Aggregation.MIN: return min(numeric)
    if metric.aggregation is Aggregation.MAX: return max(numeric)
    raise ValueError(f'unsupported aggregation: {metric.aggregation}')


def _sort_value(value: Any) -> tuple[int,str,Any]:
    if value is None: return (2,'',0)
    if isinstance(value,(int,float)) and not isinstance(value,bool): return (0,'number',float(value))
    return (1,type(value).__name__,str(value).casefold())


class Dataset:
    """Immutable row source with governed dimensions and metrics."""
    def __init__(self, key: str, rows: Sequence[Mapping[str,Any]], *, dimensions: Sequence[Dimension]=(), metrics: Sequence[Metric]=(), row_key: str | None=None):
        if not key.strip(): raise ValueError('Dataset key must not be empty')
        self.key=key; self.row_key=row_key
        self._rows=tuple(deepcopy(dict(row)) for row in rows)
        self._fields=frozenset(key for row in self._rows for key in row)
        self._indexes:dict[str,dict[Any,tuple[int,...]]]={}
        self.dimensions={item.key:item for item in dimensions}; self.metrics={item.key:item for item in metrics}
        if len(self.dimensions)!=len(tuple(dimensions)): raise ValueError('duplicate dimension key')
        if len(self.metrics)!=len(tuple(metrics)): raise ValueError('duplicate metric key')
        if row_key is not None:
            seen=set()
            for row in self._rows:
                identity=_freeze(row.get(row_key))
                if row.get(row_key) is None: raise ValueError(f'dataset rows require non-null {row_key!r}')
                if identity in seen: raise ValueError(f'duplicate dataset row identity: {row.get(row_key)!r}')
                seen.add(identity)

    @property
    def row_count(self) -> int: return len(self._rows)

    @property
    def fields(self) -> frozenset[str]: return self._fields

    @property
    def indexed_fields(self) -> frozenset[str]: return frozenset(self._indexes)

    def rows(self) -> tuple[dict[str,Any],...]: return tuple(deepcopy(row) for row in self._rows)

    def _index(self, field: str) -> dict[Any,tuple[int,...]]:
        existing=self._indexes.get(field)
        if existing is not None:return existing
        pending:dict[Any,list[int]]={}
        for index,row in enumerate(self._rows):
            key=_freeze(row.get(field)); pending.setdefault(key,[]).append(index)
        built={key:tuple(values) for key,values in pending.items()}
        self._indexes[field]=built
        return built

    def _candidate_indices(self, filters: Sequence[FilterClause]) -> tuple[int,...] | None:
        candidates:set[int]|None=None
        for clause in filters:
            values:tuple[Any,...]|None=None
            if clause.operation is FilterOperation.EQUALS:
                values=(clause.value,)
            elif clause.operation is FilterOperation.IN:
                try: values=tuple(clause.value)
                except TypeError: values=None
            if values is None:continue
            index=self._index(clause.field)
            matched:set[int]=set()
            for value in values:matched.update(index.get(_freeze(value),()))
            candidates=matched if candidates is None else candidates & matched
            if not candidates:return ()
        return None if candidates is None else tuple(sorted(candidates))

    def _filtered(self, filters: Sequence[FilterClause], search: str='', search_fields: Sequence[str]=()) -> list[Mapping[str,Any]]:
        needle=search.strip().casefold(); fields=tuple(search_fields)
        candidate_indices=self._candidate_indices(filters)
        candidates=self._rows if candidate_indices is None else (self._rows[index] for index in candidate_indices)
        result=[]
        for row in candidates:
            if filters and not all(_matches(row.get(clause.field),clause) for clause in filters): continue
            if needle:
                values=(row.get(field) for field in fields) if fields else row.values()
                if not any(needle in str(value).casefold() for value in values if value is not None): continue
            result.append(row)
        return result

    def query(self, query: DataQuery=DataQuery(), *, revision: int=0) -> DataResult:
        filtered=self._filtered(query.filters,query.search,query.search_fields)
        if query.dimensions or query.metrics:
            rows=self._group(filtered,query.dimensions,query.metrics)
        else:
            rows=[deepcopy(dict(row)) for row in filtered]
        for sort in reversed(query.sorts):
            rows.sort(key=lambda row,s=sort:_sort_value(row.get(s.key)),reverse=sort.descending)
        total=len(self._rows); filtered_total=len(filtered)
        start=query.offset; stop=None if query.limit is None else start+query.limit
        return DataResult(tuple(deepcopy(row) for row in rows[start:stop]),total=total,revision=revision,filtered_total=filtered_total)

    def _group(self, rows: Sequence[Mapping[str,Any]], dimension_keys: Sequence[str], metric_keys: Sequence[str]) -> list[dict[str,Any]]:
        dimensions=[]
        for key in dimension_keys:
            if key not in self.dimensions: raise KeyError(f'unknown dimension: {key}')
            dimensions.append(self.dimensions[key])
        metrics=[]
        for key in metric_keys:
            if key not in self.metrics: raise KeyError(f'unknown metric: {key}')
            metrics.append(self.metrics[key])
        groups: OrderedDict[tuple[Any,...],tuple[tuple[Any,...],list[Mapping[str,Any]]]]=OrderedDict()
        if not dimensions:
            groups[()]=((),list(rows))
        else:
            for row in rows:
                raw=tuple(row.get(item.source_field) for item in dimensions); frozen=tuple(_freeze(value) for value in raw)
                if frozen not in groups: groups[frozen]=(raw,[])
                groups[frozen][1].append(row)
        output=[]
        for raw, group_rows in groups.values():
            item={dimension.key:deepcopy(value) for dimension,value in zip(dimensions,raw)}
            for metric in metrics: item[metric.key]=_aggregate(metric,group_rows)
            output.append(item)
        return output


class DataBinding(Generic[T]):
    """Derived session value that recomputes once per committed filter revision."""
    def __init__(self, session: 'DataSession', resolver: Callable[['DataSession'],T]):
        self.session=session; self.resolver=resolver; self.value=resolver(session); self.revision=session.revision; self._watchers:list[BindingWatcher]=[]; self._closed=False
        self._unsubscribe=session.watch(self._session_changed)

    def _session_changed(self, session: 'DataSession') -> None:
        if self._closed:return
        self.value=self.resolver(session); self.revision=session.revision
        for watcher in tuple(self._watchers): watcher(self)

    def watch(self, callback: BindingWatcher) -> Callable[[],None]:
        self._watchers.append(callback)
        def unsubscribe():
            if callback in self._watchers:self._watchers.remove(callback)
        return unsubscribe

    def close(self) -> None:
        if self._closed:return
        self._closed=True; self._unsubscribe(); self._watchers.clear()


class DataSession:
    def __init__(self, dataset: Dataset):
        self.dataset=dataset; self._filters:dict[str,FilterClause]={}; self.search=''; self.revision=0; self._watchers:list[SessionWatcher]=[]; self._transaction_depth=0; self._dirty=False; self._closed=False
        self._bindings:list[DataBinding[Any]]=[]

    @property
    def filters(self) -> tuple[FilterClause,...]: return tuple(self._filters.values())
    @property
    def closed(self) -> bool:return self._closed

    def watch(self, callback: SessionWatcher) -> Callable[[],None]:
        if self._closed: raise RuntimeError('DataSession is closed')
        self._watchers.append(callback)
        def unsubscribe():
            if callback in self._watchers:self._watchers.remove(callback)
        return unsubscribe

    def bind(self, resolver: Callable[['DataSession'],T]) -> DataBinding[T]:
        if self._closed: raise RuntimeError('DataSession is closed')
        binding=DataBinding(self,resolver); self._bindings.append(binding); return binding

    @contextmanager
    def transaction(self):
        if self._closed: raise RuntimeError('DataSession is closed')
        self._transaction_depth+=1
        try: yield self
        finally:
            self._transaction_depth-=1
            if self._transaction_depth==0 and self._dirty:
                self._dirty=False; self._emit()

    def _changed(self) -> None:
        if self._transaction_depth:self._dirty=True
        else:self._emit()

    def _emit(self) -> None:
        self.revision+=1
        for watcher in tuple(self._watchers): watcher(self)

    def set_filter(self, clause: FilterClause) -> None:
        previous=self._filters.get(clause.key)
        if previous==clause:return
        self._filters[clause.key]=clause; self._changed()

    def clear_filter(self, filter_id: str) -> bool:
        if filter_id not in self._filters:return False
        del self._filters[filter_id]; self._changed(); return True

    def clear_filters(self) -> None:
        if not self._filters:return
        self._filters.clear(); self._changed()

    def set_search(self, search: str) -> None:
        search=str(search)
        if self.search==search:return
        self.search=search; self._changed()

    def query(self, query: DataQuery=DataQuery()) -> DataResult:
        merged_filters=tuple(self._filters.values())+tuple(query.filters)
        merged=replace(query,filters=merged_filters,search=query.search or self.search)
        return self.dataset.query(merged,revision=self.revision)

    def rows(self, *, search_fields: Sequence[str]=(), sorts: Sequence[SortClause]=(), offset: int=0, limit: int|None=None) -> DataResult:
        return self.query(DataQuery(search_fields=tuple(search_fields),sorts=tuple(sorts),offset=offset,limit=limit))

    def aggregate(self, *, dimensions: Sequence[str]=(), metrics: Sequence[str], sorts: Sequence[SortClause]=()) -> DataResult:
        return self.query(DataQuery(dimensions=tuple(dimensions),metrics=tuple(metrics),sorts=tuple(sorts)))

    def metric(self, metric: str) -> Any:
        result=self.aggregate(metrics=(metric,))
        return result.rows[0].get(metric) if result.rows else None

    def snapshot(self) -> DataSessionSnapshot:
        return DataSessionSnapshot(self.revision,tuple(deepcopy(tuple(self._filters.values()))),self.search)

    def restore(self, snapshot: DataSessionSnapshot) -> None:
        with self.transaction():
            next_filters={clause.key:deepcopy(clause) for clause in snapshot.filters}
            if self._filters!=next_filters: self._filters=next_filters; self._dirty=True
            if self.search!=snapshot.search: self.search=snapshot.search; self._dirty=True

    def close(self) -> None:
        if self._closed:return
        self._closed=True
        for binding in tuple(self._bindings): binding.close()
        self._bindings.clear(); self._watchers.clear()


class DataEngine:
    """Registry/factory authority for universal v3 datasets and filter sessions."""
    def __init__(self): self._datasets:dict[str,Dataset]={}
    @property
    def datasets(self) -> Mapping[str,Dataset]: return dict(self._datasets)
    def register(self,dataset:Dataset) -> Dataset:
        if dataset.key in self._datasets: raise ValueError(f'dataset already registered: {dataset.key}')
        self._datasets[dataset.key]=dataset; return dataset
    def unregister(self,key:str) -> None:self._datasets.pop(key,None)
    def get(self,key:str) -> Dataset:
        try:return self._datasets[key]
        except KeyError:raise KeyError(f'unknown dataset: {key}') from None
    def session(self,key:str) -> DataSession:return DataSession(self.get(key))
