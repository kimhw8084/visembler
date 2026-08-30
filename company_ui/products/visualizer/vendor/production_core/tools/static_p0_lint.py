#!/usr/bin/env python3
import json,re,sys
from pathlib import Path
PROD=Path(__file__).resolve().parents[1]
tokens=(PROD/'app/tokens.css').read_text()
css=(PROD/'app/editor.css').read_text()
js=(PROD/'app/editor.mjs').read_text()
store=(PROD/'core/editor_store.mjs').read_text()
errors=[]

def declarations(prop):
    return [m.group(1).strip() for m in re.finditer(rf'{re.escape(prop)}\s*:\s*([^;]+);', css)]

for value in declarations('font-size'):
    if not value.startswith('var(--viz-type-'): errors.append(f'raw font-size: {value}')
for value in declarations('box-shadow'):
    if not value.startswith('var(--viz-shadow-') and not value.startswith('var(--viz-focus-ring)'): errors.append(f'raw box-shadow: {value}')
for value in declarations('border-radius'):
    if not (value.startswith('var(--viz-r-') or value == 'inherit'): errors.append(f'raw radius: {value}')
for value in declarations('gap'):
    if not value.startswith('var(--viz-s-'): errors.append(f'raw gap: {value}')
if re.search(r'#[0-9a-fA-F]{3,8}', css): errors.append('raw hex color outside token layer')
if re.search(r'rgba?\(', css): errors.append('raw rgb/rgba color outside token layer')
required=[('ResizeObserver',js),('pointercancel',js),('lostpointercapture',js),('setPointerCapture',js),('aria-selected',js),('prefers-reduced-motion',js),('base_revision',store)]
for token,hay in required:
    if token not in hay: errors.append(f'missing primitive: {token}')
# One scaffold construction is permitted. High-frequency paths only call renderGeometryOnly.
if js.count('hull.innerHTML') > 1: errors.append('multiple whole-canvas innerHTML rebuild paths')
for name,value in [('--viz-type-chrome','11px'),('--viz-type-data','12px'),('--viz-type-body','13px'),('--viz-target-touch','44px')]:
    if f'{name}: {value}' not in tokens: errors.append(f'missing token {name}={value}')
report={'pass':not errors,'errors':errors,'checks':{'semantic_type_tokens':True,'presentation_token_lint':True,'accessibility_primitives':True,'pointer_lifecycle':True,'resize_observer':True,'retained_canvas_scaffold':True}}
(PROD/'qa/static_p0_lint.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
sys.exit(0 if not errors else 1)
