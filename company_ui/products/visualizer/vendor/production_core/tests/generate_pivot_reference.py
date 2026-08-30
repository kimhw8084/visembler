import json, random
from pathlib import Path
import pandas as pd

random.seed(4172026)
rows=[]
sites=['S1','S2','S3','S4']
tools=['T1','T2','T3','T4','T5']
quarters=['Q1','Q2','Q3','Q4']
products=['A','B','C']
for i in range(1500):
    rows.append({
        'site': random.choice(sites),
        'tool': random.choice(tools),
        'quarter': random.choice(quarters),
        'product': random.choice(products),
        'amount': random.randint(0, 10000),
        'defects': random.randint(0, 30),
        'lot': f"L{random.randint(1,120)}",
    })
df=pd.DataFrame(rows)
row_prefixes=[[],['site'],['site','tool']]
col_prefixes=[[],['quarter'],['quarter','product']]
expected=[]

def unique_paths(cols):
    if not cols: return [()]
    return sorted([tuple(x) for x in df[cols].drop_duplicates().itertuples(index=False, name=None)])

for rcols in row_prefixes:
    for rpath in unique_paths(rcols):
        mask=pd.Series(True,index=df.index)
        for c,v in zip(rcols,rpath): mask &= df[c].eq(v)
        rdf=df[mask]
        for ccols in col_prefixes:
            for cpath in unique_paths(ccols):
                cmask=pd.Series(True,index=rdf.index)
                for c,v in zip(ccols,cpath): cmask &= rdf[c].eq(v)
                x=rdf[cmask]
                if x.empty: continue
                expected.append({
                    'row_path':list(rpath),'column_path':list(cpath),
                    'rev_sum':int(x['amount'].sum()),
                    'def_avg':float(x['defects'].mean()),
                    'lot_distinct':int(x['lot'].nunique()),
                    'n':int(x['amount'].count()),
                })
out={'reference':'pandas 2.2.3','seed':4172026,'rows':rows,'expected':expected}
p=Path(__file__).parent/'fixtures'/'pivot_reference.json'
p.write_text(json.dumps(out,separators=(',',':')),encoding='utf-8')
print(json.dumps({'pass':True,'rows':len(rows),'expected_cells':len(expected),'path':str(p)},indent=2))
