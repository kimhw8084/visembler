#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path
PROD=Path(__file__).resolve().parents[1]
def strip(src): return re.sub(r'^import .*?;\s*$','',src,flags=re.M).replace('export const ','const ').replace('export function ','function ').replace('export class ','class ')
rt=strip((PROD/'core/runtime_registry.mjs').read_text())+'\nglobalThis.__REG={ELEMENTS_BY_ENGINE,ALL_ELEMENTS};'
ur=strip((PROD/'core/universal_renderer.mjs').read_text())+'\nglobalThis.__RENDER={renderElement,findEngineForElement,renderEngineGallery,renderAllElements};'
gl=strip((PROD/'core/grid_layout_engine.mjs').read_text())+'\nglobalThis.__GRID={compileGridLayout,findLargestEmptyRegion,mapPlacementToRegion};'
dg=strip((PROD/'core/data_grid_engine.mjs').read_text())+'\nglobalThis.__DATA={prepareDataGrid,gridVirtualWindow,rowAt};'
pv=re.sub(r'^import .*?;\s*$','',(PROD/'app/approval/preview.mjs').read_text(),flags=re.M)
pv="const {ELEMENTS_BY_ENGINE}=globalThis.__REG; const {renderElement}=globalThis.__RENDER; const {compileGridLayout,findLargestEmptyRegion}=globalThis.__GRID; const {prepareDataGrid,gridVirtualWindow}=globalThis.__DATA;\n"+pv
js=';\n'.join([f'(()=>{{{rt}}})()',f'(()=>{{const {{ELEMENTS_BY_ENGINE}}=globalThis.__REG;{ur}}})()',f'(()=>{{{gl}}})()',f'(()=>{{{dg}}})()',pv])
html=(PROD/'app/approval/index.html').read_text();css=(PROD/'app/tokens.css').read_text()+(PROD/'app/approval/preview.css').read_text().replace("@import url('../tokens.css');",'')
out=html.replace('<link rel="stylesheet" href="./preview.css">',f'<style>{css}</style>').replace('<script type="module" src="./preview.mjs"></script>',f'<script>{js}</script>')
(PROD/'APPROVAL_PREVIEW_STANDALONE.html').write_text(out)
print(PROD/'APPROVAL_PREVIEW_STANDALONE.html')
