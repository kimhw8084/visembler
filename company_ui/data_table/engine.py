from __future__ import annotations
import csv, io
from collections import OrderedDict
from typing import Any, Iterable, Mapping, Sequence
from .models import FilterOperator, FilterSpec, SortDirection, TableColumn, TableQuery, TableResult

def _norm(v:Any)->Any:return '' if v is None else v

def _compile_filter(spec:FilterSpec):
    op=spec.operator; b=spec.value; bset=set(b or ()) if op is FilterOperator.IN else None; needle=str(b).lower() if op in {FilterOperator.CONTAINS,FilterOperator.STARTS_WITH,FilterOperator.ENDS_WITH} else None
    def match(value):
        a=_norm(value)
        if op is FilterOperator.IS_EMPTY:return value is None or value==''
        if op is FilterOperator.IS_NOT_EMPTY:return not(value is None or value=='')
        if op is FilterOperator.CONTAINS:return needle in str(a).lower()
        if op is FilterOperator.STARTS_WITH:return str(a).lower().startswith(needle)
        if op is FilterOperator.ENDS_WITH:return str(a).lower().endswith(needle)
        if op is FilterOperator.EQUALS:return a==b
        if op is FilterOperator.NOT_EQUALS:return a!=b
        if op is FilterOperator.IN:return a in bset
        try:
            if op is FilterOperator.GT:return a>b
            if op is FilterOperator.GTE:return a>=b
            if op is FilterOperator.LT:return a<b
            if op is FilterOperator.LTE:return a<=b
            if op is FilterOperator.BETWEEN:return b<=a<=spec.value2
        except TypeError:return False
        return True
    return spec.key,match

def _sort_value(v:Any):
    if v is None:return (1,'','')
    if isinstance(v,(int,float,str,bool)):return (0,type(v).__name__,v)
    return (0,type(v).__name__,str(v))

def _filtered_sorted(rows, query:TableQuery, searchable_columns:Sequence[str]|None=None, search_index:Sequence[str]|None=None):
    needle=query.search.lower().strip(); compiled=tuple(_compile_filter(f) for f in query.filters); out=[]
    allowed=set(searchable_columns) if searchable_columns is not None else None
    one = compiled[0] if len(compiled)==1 else None
    if search_index is not None and needle:
        for idx,r in enumerate(rows):
            if needle not in search_index[idx]: continue
            if one is not None:
                if not one[1](r.get(one[0])): continue
            elif compiled and not all(fn(r.get(key)) for key,fn in compiled): continue
            out.append(r)
    else:
        for r in rows:
            if needle and not any(needle in str(v).lower() for k,v in r.items() if allowed is None or k in allowed): continue
            if one is not None:
                if not one[1](r.get(one[0])): continue
            elif compiled and not all(fn(r.get(key)) for key,fn in compiled): continue
            out.append(r)
    for spec in reversed(query.sorts):
        nonnull=[r for r in out if r.get(spec.key) is not None]; nulls=[r for r in out if r.get(spec.key) is None]
        try:
            nonnull.sort(key=lambda r:r.get(spec.key), reverse=spec.direction is SortDirection.DESC)
        except TypeError:
            nonnull.sort(key=lambda r:(type(r.get(spec.key)).__name__,str(r.get(spec.key))), reverse=spec.direction is SortDirection.DESC)
        out=nonnull+nulls
    return out

def apply_query(rows:Iterable[Mapping[str,Any]],query:TableQuery,*,searchable_columns:Sequence[str]|None=None)->TableResult:
    data=list(rows); data=_filtered_sorted(data,query,searchable_columns); total=len(data); start=(query.page-1)*query.page_size; return TableResult(tuple(data[start:start+query.page_size]),total,query.page,query.page_size)

def _freeze(v):
    if isinstance(v,dict):return tuple(sorted((k,_freeze(x)) for k,x in v.items()))
    if isinstance(v,(list,tuple,set)):return tuple(_freeze(x) for x in v)
    try:hash(v); return v
    except TypeError:return repr(v)

def _query_key(q:TableQuery,*,include_page=True):
    base=(q.search,tuple((s.key,s.direction.value) for s in q.sorts),tuple((f.key,f.operator.value,_freeze(f.value),_freeze(f.value2)) for f in q.filters),q.page_size)
    return base+(q.page,) if include_page else base

class TableQueryEngine:
    """Bounded repeated-query engine for stable in-memory datasets."""
    def __init__(self, rows:Iterable[Mapping[str,Any]], *, searchable_columns:Sequence[str]|None=None, max_cached_queries:int=32, build_search_index:bool=True):
        self.rows=tuple(rows); self.searchable_columns=tuple(searchable_columns) if searchable_columns is not None else None; self.max_cached_queries=max_cached_queries; self._cache=OrderedDict(); self._search_index=None
        if build_search_index:
            allowed=set(self.searchable_columns) if self.searchable_columns is not None else None
            self._search_index=tuple(' '.join(str(v).lower() for k,v in r.items() if allowed is None or k in allowed) for r in self.rows)
    def query(self,q:TableQuery)->TableResult:
        base=_query_key(q,include_page=False); data=self._cache.get(base)
        if data is None:
            data=tuple(_filtered_sorted(self.rows,q,self.searchable_columns,self._search_index)); self._cache[base]=data; self._cache.move_to_end(base)
            while len(self._cache)>self.max_cached_queries:self._cache.popitem(last=False)
        else:self._cache.move_to_end(base)
        start=(q.page-1)*q.page_size; return TableResult(tuple(data[start:start+q.page_size]),len(data),q.page,q.page_size)
    def clear(self):self._cache.clear()

def format_cell(value:Any,column:TableColumn)->str:
    if value is None:return '—'
    if column.kind.value=='percent':d=column.decimals if column.decimals is not None else 1; return f'{float(value):.{d}f}%'
    if column.kind.value=='float':d=column.decimals if column.decimals is not None else 2; txt=f'{float(value):,.{d}f}'
    elif column.kind.value=='integer':txt=f'{int(value):,}'
    elif column.kind.value=='boolean':txt='Yes' if bool(value) else 'No'
    elif column.kind.value=='datetime':txt=value.strftime('%Y-%m-%d %H:%M') if hasattr(value,'strftime') else str(value)
    else:txt=str(value)
    return f'{txt} {column.unit}'.strip() if column.unit else txt

def _excel_safe(text:str)->str:
    stripped=text.lstrip()
    return "'"+text if stripped.startswith(('=','+','-','@')) else text

def export_csv(rows:Iterable[Mapping[str,Any]],columns:Sequence[TableColumn])->str:
    visible=[c for c in columns if c.visible and c.kind.value!='action']; stream=io.StringIO(); writer=csv.writer(stream); writer.writerow([c.label for c in visible])
    for row in rows:
        cells=[]
        for c in visible:
            text=format_cell(row.get(c.key),c); cells.append(_excel_safe(text) if c.kind.value in {'text','link','status','custom'} else text)
        writer.writerow(cells)
    return stream.getvalue()
__all__=['TableQueryEngine','apply_query','format_cell','export_csv']
