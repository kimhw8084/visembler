#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys
from pathlib import Path
PROD=Path(__file__).resolve().parents[1]
scan=[PROD/'app',PROD/'core']
external=[];cdn=[]
for root in scan:
    for p in root.rglob('*'):
        if p.suffix.lower() not in {'.js','.mjs','.css','.html','.json'}: continue
        t=p.read_text(errors='ignore')
        for m in re.finditer(r'https?://[^\s\"\'<>]+',t):
            url=m.group(0)
            if url.startswith('http://www.w3.org/2000/svg'):
                continue
            external.append({'file':str(p.relative_to(PROD)),'url':url})
        if re.search(r'cdn\.|unpkg|jsdelivr|cdnjs|googleapis|fonts\.google',t,re.I): cdn.append(str(p.relative_to(PROD)))
report={'pass':not external and not cdn,'external_urls':external,'cdn_references':sorted(set(cdn)),'local_module_preview':True,'runtime_node_required':False}
(PROD/'qa/offline_runtime.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));sys.exit(0 if report['pass'] else 1)
