#!/usr/bin/env python3
"""Build the secret-free CHG-137 R2 evidence package outside Product source."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = 'a7d5b18ea471ec5ee4b33983175625296d27c07f'
BASE_TREE = 'a0cc41cdb119b8375d5bea5aa90e806b2e15f811'
PREDECESSOR = 'b7a59a1acf50c57ed1954fe1a57215599ae32e86'
PREDECESSOR_TREE = '9cfcf0bbdbd1de646a17ce9a6e5915dd55522451'
PREDECESSOR_EVIDENCE = '7a259d711ea003aae4bc827c60aa26ac892fbfcf'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def node_probe() -> dict:
    source = r'''
import {chartModelFromEntry, chartRenderPlan, canonicalBarRectangles, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const fields=[{id:'category',name:'Category',type:'categorical'},{id:'series',name:'Series',type:'categorical'},{id:'value',name:'Value',type:'number'}];
const fixtures=[
  ['vertical-grouped-positive','Vertical Bar',[['A','one',2],['B','one',5]],'grouped',{}],
  ['vertical-grouped-negative','Vertical Bar',[['A','one',-2],['B','one',-5]],'grouped',{}],
  ['vertical-mixed','Vertical Bar',[['A','one',-2],['B','one',5]],'grouped',{}],
  ['vertical-stacked','Vertical Bar',[['A','one',4],['A','two',3],['B','one',-2],['B','two',-5]],'stacked',{}],
  ['vertical-percent','Vertical Bar',[['A','one',4],['A','two',6],['B','one',1],['B','two',3]],'percent',{}],
  ['horizontal-grouped','Horizontal Bar',[['A','one',2],['B','one',5]],'grouped',{}],
  ['horizontal-stacked','Horizontal Bar',[['A','one',4],['A','two',3],['B','one',-2],['B','two',-5]],'stacked',{}],
  ['horizontal-percent','Horizontal Bar',[['A','one',4],['A','two',6],['B','one',1],['B','two',3]],'percent',{}],
  ['configured-domain','Vertical Bar',[['A','one',2],['B','one',5]],'grouped',{y:{min:-10,max:10,zeroBaseline:true}}],
];
const parseRects=svg=>[...svg.matchAll(/<rect class="cs-mark cs-bar-mark"[^>]*\bx="([\d.-]+)"[^>]*\by="([\d.-]+)"[^>]*\bwidth="([\d.-]+)"[^>]*\bheight="([\d.-]+)"/g)].map(m=>({x:Number(m[1]),y:Number(m[2]),width:Number(m[3]),height:Number(m[4])}));
const result={fixtures:{},summary:{tolerance:.011}};
for(const [name,type,rows,barMode,yAxes] of fixtures){
  const dataset={id:name,fields,rows},model=chartModelFromEntry({element:type,mapping:{category:'category',value:'value',series:'series'},visual:{barMode},axes:yAxes.y?yAxes:{y:yAxes},dataset},dataset),options={width:860,height:460},plan=chartRenderPlan(model,options),exposed=canonicalBarRectangles(model,options),rendered=parseRects(renderChartSvg(model,options));
  const rects=exposed.map((rect,index)=>{const horizontal=type==='Horizontal Bar',start=horizontal?plan.valueAt(rect.base):plan.yAt(rect.base),end=horizontal?plan.valueAt(rect.end):plan.yAt(rect.end),expected=horizontal?{x:Math.min(start,end),y:rect.y,width:Math.abs(start-end),height:rect.height}:{x:rect.x,y:Math.min(start,end),width:rect.width,height:Math.abs(start-end)},actual={x:rect.x,y:rect.y,width:rect.width,height:rect.height},svg=rendered[index]||null,delta=Object.fromEntries(Object.keys(expected).map(key=>[key,Math.abs(actual[key]-expected[key])])),svgDelta=svg?Object.fromEntries(Object.keys(actual).map(key=>[key,Math.abs(actual[key]-svg[key])])):null;return {category:rect.category,series:rect.series,sourceIndex:rect.sourceIndex,base:rect.base,end:rect.end,display:rect.display,expected,actual,svg,delta,svgDelta};});
  result.fixtures[name]={orientation:type==='Horizontal Bar'?'horizontal':'vertical',domain:plan.yDomain,rects,finite:rects.every(rect=>Object.values(rect.delta).every(Number.isFinite)&&rect.svgDelta&&Object.values(rect.svgDelta).every(value=>value<=.011))};
}
result.fixtures['vertical-stacked'].later_positive_segment=result.fixtures['vertical-stacked'].rects.find(rect=>rect.category==='A'&&rect.series==='two')||null;
result.fixtures['horizontal-stacked'].later_positive_segment=result.fixtures['horizontal-stacked'].rects.find(rect=>rect.category==='A'&&rect.series==='two')||null;
result.fixtures['vertical-percent'].later_percent_segment=result.fixtures['vertical-percent'].rects.find(rect=>rect.category==='A'&&rect.series==='two')||null;
console.log(JSON.stringify(result));
'''
    completed = subprocess.run(['node', '--input-type=module', '-'], cwd=ROOT, input=source, text=True, capture_output=True, check=True)
    return json.loads(completed.stdout)


def authority_probe() -> dict:
    source = r'''
import {CORE_TYPES, chartModelFromEntry, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
import {readFile} from 'node:fs/promises';
const dataset={id:'authority',fields:[{id:'x',name:'X',type:'number'},{id:'y',name:'Y',type:'number'}],rows:[[0,1],[2,3],[10,4]]};
const output=Object.fromEntries(CORE_TYPES.map(type=>{const mapping=['Vertical Bar','Horizontal Bar','Pareto'].includes(type)?{category:'x',value:'y'}:['Histogram','Box Plot'].includes(type)?{value:'y'}:{x:'x',y:'y'};const model=chartModelFromEntry({element:type,mapping,dataset},dataset),entry={id:'authority',engine:'CoreChartEngine',element:type,title:type,mapping,_resolved_dataset:dataset};return [type,{chart_studio:renderChartSvg(model,{width:760,height:400}).includes('data-renderer-authority="visembler-canonical-chart-v2"'),integrated_editor:renderIntegratedElement(entry).includes('data-renderer-authority="visembler-canonical-chart-v2"')}]}));
const source=await readFile('./company_ui/products/visualizer/assets/element_renderer.mjs','utf8');
console.log(JSON.stringify({core_types:output,legacy_overlapping_return:source.includes("case 'CoreChartEngine': return chart(entry);"),legacy_non_core_guard:source.includes('Legacy library-only chart previews'),canonical_route_before_switch:source.includes("if(['CoreChartEngine','EngineeringChartEngine','WaferFabEngine'].includes(entry?.engine)&&CHART_TYPES.includes(entry?.element)) return renderChartStudioElement(entry,entry._resolved_dataset||{});")}));
'''
    completed = subprocess.run(['node', '--input-type=module', '-'], cwd=ROOT, input=source, text=True, capture_output=True, check=True)
    return json.loads(completed.stdout)


def copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    for path in sorted(source.rglob('*')):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def write_deterministic_bundle(output: Path, bundle: Path) -> None:
    raw = bytearray()
    with tarfile.open(fileobj=__import__('io').BytesIO(), mode='w') as unused:
        pass
    stream = __import__('io').BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                info = archive.gettarinfo(str(path), arcname=Path(output.name) / path.relative_to(output))
                info.mtime = 0
                with path.open('rb') as handle:
                    archive.addfile(info, handle)
    bundle.write_bytes(gzip.compress(stream.getvalue(), compresslevel=9, mtime=0))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--acceptance', type=Path, required=True)
    parser.add_argument('--base-browser', type=Path, required=True)
    parser.add_argument('--candidate-browser', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    reports = output / 'reports';screens = output / 'screenshots';reports.mkdir(parents=True);screens.mkdir()
    for label, source in (('base', args.base_browser), ('candidate', args.candidate_browser)):
        copy_tree(source / 'screenshots', screens / label)
        for report in sorted(source.glob('*.json')):
            shutil.copy2(report, reports / f'{label}-{report.name}')
    shutil.copy2(args.acceptance, reports / 'chart-studio-acceptance.json')

    geometry = node_probe();authority = authority_probe()
    (reports / 'bar-geometry-probe.json').write_text(json.dumps(geometry, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (reports / 'source-authority.json').write_text(json.dumps(authority, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (reports / 'domain-scale-probes.json').write_text(json.dumps({'source': 'tests/test_visualizer_chart_renderer_r1.py and canonical renderer probe', 'geometry_domains': {key:value['domain'] for key,value in geometry['fixtures'].items()}, 'configured_domain': geometry['fixtures']['configured-domain']['domain'], 'percent_domain': geometry['fixtures']['vertical-percent']['domain'], 'finite_all_fixtures': all(value['finite'] for value in geometry['fixtures'].values())}, indent=2) + '\n', encoding='utf-8')
    acceptance = json.loads((reports / 'chart-studio-acceptance.json').read_text(encoding='utf-8'))
    candidate_browser = json.loads((reports / 'candidate-candidate-r2-browser-acceptance.json').read_text(encoding='utf-8'))
    live_export = {'candidate_browser_export_check': next((row.get('details') for row in candidate_browser['checks'] if row['name'] == 'SVG export canonical parity'), None), 'authority_marker': authority['canonical_route_before_switch'], 'chart_studio_and_integrated_core_types': all(value['chart_studio'] and value['integrated_editor'] for value in authority['core_types'].values())}
    (reports / 'live-export-parity.json').write_text(json.dumps(live_export, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    interaction = {'native_acceptance': {'pass': acceptance.get('pass'), 'applicable': acceptance.get('applicable'), 'not_applicable': acceptance.get('not_applicable'), 'unexpected_errors': acceptance.get('unexpected_errors', [])}, 'candidate_r2_browser': {'pass': candidate_browser.get('pass'), 'applicable': candidate_browser.get('applicable'), 'errors': candidate_browser.get('errors', []), 'checks': candidate_browser.get('checks', [])}}
    (reports / 'interaction-accessibility.json').write_text(json.dumps(interaction, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    source_files = ['company_ui/products/visualizer/assets/canonical_chart_renderer.mjs','company_ui/products/visualizer/assets/authoring_chart_studio.mjs','company_ui/products/visualizer/assets/chart_studio.mjs','company_ui/products/visualizer/assets/element_renderer.mjs','company_ui/products/visualizer/assets/integrated_editor.mjs','company_ui/products/visualizer/page.py','scripts/release_checks/run_chart_studio_acceptance.py','scripts/release_checks/run_chart_renderer_r2_acceptance.py','scripts/release_checks/build_chart_r2_evidence.py','tests/test_visualizer_chart_renderer_r1.py','tests/test_visualizer_chart_renderer_r2.py','company_ui/certification/certification_manifest.json']
    source_manifest = {relative: sha256(ROOT / relative) for relative in source_files if (ROOT / relative).is_file()}
    candidate = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip();candidate_tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip();branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip();candidate_timestamp = subprocess.check_output(['git', 'show', '-s', '--format=%cI', candidate], cwd=ROOT, text=True).strip()
    artifacts = []
    for path in sorted(output.rglob('*')):
        if path.is_file() and path.name != 'manifest.json':
            artifacts.append({'path': path.relative_to(output).as_posix(), 'sha256': sha256(path), 'bytes': path.stat().st_size})
    manifest = {'schema_version': 2, 'project': 'visembler', 'request': 'CHG-137-r2', 'source_change': 'CHG-137', 'operation': 'FIX', 'job': 'CF-cc68ea8cca82c915c44a0809', 'scope': 'bounded CHG-137 R2 chart renderer correction', 'created_at': candidate_timestamp, 'base_commit': BASE, 'base_tree': BASE_TREE, 'candidate_commit': candidate, 'candidate_tree': candidate_tree, 'work_branch': branch, 'target': candidate, 'head': candidate, 'predecessor': {'commit': PREDECESSOR, 'tree': PREDECESSOR_TREE, 'evidence_commit': PREDECESSOR_EVIDENCE}, 'working_tree_status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True).splitlines(), 'source_files': source_manifest, 'artifacts': artifacts, 'artifact_bridge': {'status': 'STAGED', 'transport': 'bounded-dashboard-managed-Notion-fallback', 'semantic_scope': 'canonical CHG-137-r2 Artifact Run only'}, 'promotion': {'integrated': False, 'visual_surfaces_updated': False, 'gold_candidate_claimed': False, 'go_claimed': False}, 'holdouts': {'base_is_evidence_only': True, 'r1_rejected_candidate_is_not_fabric_envelope_base': True, 'specialized_statistical_engineering_waferfab_authorities_retained': True}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    bundle = output.parent / 'CHG-137-r2-evidence.tar.gz';write_deterministic_bundle(output, bundle)
    print(json.dumps({'manifest': str(output / 'manifest.json'), 'manifest_sha256': sha256(output / 'manifest.json'), 'bundle': str(bundle), 'bundle_sha256': sha256(bundle), 'artifact_count': len(artifacts), 'artifact_bytes': sum(item['bytes'] for item in artifacts), 'candidate_commit': candidate, 'candidate_tree': candidate_tree}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
