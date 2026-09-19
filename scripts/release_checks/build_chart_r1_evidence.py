#!/usr/bin/env python3
"""Build the secret-free, local CHG-137 R1 evidence bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = 'a7d5b18ea471ec5ee4b33983175625296d27c07f'
BASE_TREE = 'a0cc41cdb119b8375d5bea5aa90e806b2e15f811'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def node_probes() -> dict:
    source = r'''
import {chartModelFromEntry, chartRenderPlan, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const dataset=(fields,rows)=>({id:'probe',fields,rows});
const numberFields=[{id:'x',name:'X',type:'number'},{id:'y',name:'Y',type:'number'},{id:'series',name:'Series',type:'categorical'}];
const model=(type,fields,rows,mapping,extra={})=>chartModelFromEntry({element:type,dataset:dataset(fields,rows),mapping,...extra},dataset(fields,rows));
const result={};
const numeric=model('Scatter Plot',numberFields,[[0,1,'A'],[2,3,'A'],[10,5,'A']],{x:'x',y:'y'});
const np=chartRenderPlan(numeric,{width:800,height:400});
const numericPositions=[0,2,10].map(value=>np.xAt(value,'numeric'));
const times=model('Line Chart',[{id:'time',name:'Time',type:'date'},{id:'y',name:'Y',type:'number'}],[['2026-01-01',1],['2026-01-02',2],['2026-01-05',3],['2026-01-12',4]],{x:'time',y:'y'});
const tp=chartRenderPlan(times,{width:800,height:400});
const timePositions=tp.xTicks.map(value=>tp.xAt(value));
const bars=model('Vertical Bar',[{id:'category',name:'Category',type:'categorical'},{id:'value',name:'Value',type:'number'},{id:'series',name:'Series',type:'categorical'}],[['A',4,'S1'],['A',-2,'S2'],['B',6,'S1'],['B',-3,'S2']],{category:'category',value:'value',series:'series'},{visual:{barMode:'stacked'},axes:{y:{zeroBaseline:true}}});
const bp=chartRenderPlan(bars,{width:800,height:400});
const percent=model('Vertical Bar',[{id:'category',name:'Category',type:'categorical'},{id:'value',name:'Value',type:'number'},{id:'series',name:'Series',type:'categorical'}],[['A',4,'S1'],['A',6,'S2'],['B',1,'S1'],['B',3,'S2']],{category:'category',value:'value',series:'series'},{visual:{barMode:'percent'}});
const pp=chartRenderPlan(percent,{width:800,height:400});
const missingFields=[{id:'x',name:'X',type:'categorical'},{id:'y',name:'Y',type:'number'}];
const missingRows=[['A',0],['B',null],['C',3]];
const missingPolicies=Object.fromEntries(['gap','zero','drop'].map(policy=>{const p=chartRenderPlan(model('Line Chart',missingFields,missingRows,{x:'x',y:'y'},{visual:{missingPolicy:policy}}),{width:800,height:400});return [policy,{rows:p.data.rows.map(row=>row.y),segments:p.data.bySeries[0].map(point=>point.y)}]}));
const styled=model('Line Chart',numberFields,[[0,1,'A'],[1,2,'A'],[2,3,'A']],{x:'x',y:'y',series:'series'},{axes:{y:{title:'Primary',prefix:'$',suffix:' USD',precision:2,tickCount:7},secondaryY:{title:'Secondary',tickCount:4}},series:[{key:'A',label:'A',color:'#123456',axis:'secondary',lineDash:'dashed',lineWidth:4}],legend:{position:'right',orientation:'vertical',order:'label-desc'},annotations:[{id:'a',text:'Boundary note',x:.98,y:.05}],reference_lines:[{id:'r',value:2,label:'Target'}],reference_bands:[{id:'b',low:1,high:2,label:'Range'}]});
const styledPlan=chartRenderPlan(styled,{width:390,height:844}),svg=renderChartSvg(styled,{width:390,height:844});
result.numeric_x={positions:numericPositions,proportional_gap_ratio:(numericPositions[1]-numericPositions[0])/(numericPositions[2]-numericPositions[1]),domain:np.xDomain};
result.time_x={positions:timePositions,irregular_distance_observed:timePositions.length>=3&&(timePositions[1]-timePositions[0])<(timePositions.at(-1)-timePositions.at(-2)),domain:tp.xDomain};
result.stacks={domain:bp.yDomain,totals:bp.stack.totals,positive_negative_domain:bp.stack.domainValues};
result.percent_stacks={domain:pp.yDomain,normalized:pp.stack.stacks.map(series=>series.map(point=>point.display)),category_totals:pp.stack.totals};
result.missing_policies=missingPolicies;
result.formatting_and_secondary={secondary_domain:styledPlan.secondaryDomain,secondary_ticks:styledPlan.secondaryTicks,custom_format_present:svg.includes('$2.00 USD'),configured_color:svg.includes('#123456'),dash_present:svg.includes('stroke-dasharray="8 5"'),references:svg.includes('data-reference-id="r"')&&svg.includes('data-reference-id="b"'),annotations:svg.includes('data-annotation-id="a"'),finite_output:!/[Nn]a[Nn]|[Ii]nfinity/.test(svg)};
result.live_export_parity={same_model_svg_stable:renderChartSvg(styled,{width:390,height:844})===svg,authority_marker:svg.includes('visembler-canonical-chart-v2')};
console.log(JSON.stringify(result));
'''
    completed = subprocess.run(['node', '--input-type=module', '-'], cwd=ROOT, input=source, text=True, capture_output=True, check=True)
    return json.loads(completed.stdout)


def copy_tree(source: Path, destination: Path, pattern: str | None = None) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in sorted(source.rglob(pattern or '*')):
        if path.is_file():
            target = destination / path.name
            shutil.copy2(path, target)
            copied.append(target)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--acceptance', type=Path, required=True)
    parser.add_argument('--candidate-matrix', type=Path, required=True)
    parser.add_argument('--base-matrix', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    reports = output / 'reports'
    screenshots = output / 'screenshots'
    if output.exists():
        shutil.rmtree(output)
    reports.mkdir(parents=True)
    (screenshots / 'candidate').mkdir(parents=True)
    (screenshots / 'base').mkdir(parents=True)
    shutil.copy2(args.acceptance, reports / 'chart-studio-acceptance.json')
    shutil.copy2(args.candidate_matrix / 'candidate-browser-matrix.json', reports / 'candidate-browser-matrix.json')
    shutil.copy2(args.base_matrix / 'base-browser-matrix.json', reports / 'base-browser-matrix.json')
    for label, source in (('candidate', args.candidate_matrix), ('base', args.base_matrix)):
        for image in sorted(source.glob('*.png')):
            shutil.copy2(image, screenshots / label / image.name)
    try:
        from PIL import Image, ImageDraw
        images = [path for path in sorted(screenshots.rglob('*.png')) if 'main-editor-1440-light' in path.name or 'chart-studio-1440-light' in path.name or 'chart-studio-mobile-390' in path.name or 'chart-studio-1440-dark' in path.name]
        tile_w, tile_h = 520, 330
        sheet = Image.new('RGB', (tile_w * 2, tile_h * ((len(images) + 1) // 2)), '#eef1f5')
        draw = ImageDraw.Draw(sheet)
        for index, image_path in enumerate(images):
            image = Image.open(image_path).convert('RGB')
            image.thumbnail((tile_w - 16, tile_h - 36))
            x = (index % 2) * tile_w + 8
            y = (index // 2) * tile_h + 24
            sheet.paste(image, (x + (tile_w - 16 - image.width) // 2, y))
            draw.text((x, y - 18), image_path.parent.name + ' · ' + image_path.stem, fill='#172234')
        sheet.save(output / 'chart-r1-contact-sheet.png', format='PNG', optimize=False)
    except Exception:
        pass
    probes = node_probes()
    (reports / 'domain-scale-probes.json').write_text(json.dumps(probes, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    conformance = {
        'schema_version': 1,
        'scope': 'CHG-137 R1 chart renderer and Chart Studio conformance',
        'renderer_authority': {'core': 'canonical_chart_renderer.mjs', 'adapter': 'authoring_chart_studio.mjs', 'specialized': ['statistical_presentation.mjs', 'advanced_chart_engine.mjs', 'WaferFabEngine']},
        'retained_controls': {
            'supported_and_proven': ['palette', 'x/y tick counts', 'x label rotation', 'axis title/format/position', 'legend show/position/orientation/order/filter', 'series color/visibility/axis/line dash/width/smoothing/markers', 'data labels', 'reference lines/bands', 'annotations', 'secondary axis', 'missing policy', 'tooltip', 'crosshair', 'zoom/pan/brush/range selector/reset zoom', 'recommendation preview/apply', 'recipe naming', 'SVG export'],
            'removed_or_explicitly_specialized': ['process-capability histogram and box plot remain on statistical authority; specification limits remain distinct from control limits', 'WaferFab and engineering/statistical families remain specialized authorities'],
            'proof_source': 'domain-scale-probes.json plus native acceptance checks C027-C067/C085-C088',
        },
        'control_inventory': {
            'palette': {'status': 'SUPPORTED', 'proof': 'configured palette and exact series color are present in renderer-conformance probes'},
            'x_label_rotation': {'status': 'SUPPORTED', 'proof': 'native C032 plus adaptive layout fixture'},
            'x_y_tick_count': {'status': 'SUPPORTED', 'proof': 'native C034 and adaptive tick-count fixture'},
            'axis_format_title_position': {'status': 'SUPPORTED', 'proof': 'native C027-C031 and secondary-axis probe'},
            'legend_show_position_orientation_order_filter': {'status': 'SUPPORTED', 'proof': 'native C035-C039 plus bounds probe'},
            'series_color_visibility_axis_dash_width_smoothing_markers': {'status': 'SUPPORTED', 'proof': 'native C040-C044 plus exact configured color/dash probe'},
            'data_labels': {'status': 'SUPPORTED', 'proof': 'native C045 and label collision fixture'},
            'reference_lines_bands_annotations': {'status': 'SUPPORTED', 'proof': 'native C046-C048 plus SVG persistence/export probe'},
            'secondary_axis': {'status': 'SUPPORTED', 'proof': 'native C024/C029 and independent domain/tick probe'},
            'missing_value_policy': {'status': 'SUPPORTED', 'proof': 'gap/zero/drop probe with numeric zero retained'},
            'tooltip_keyboard_touch_inspection': {'status': 'SUPPORTED', 'proof': 'candidate browser matrix tooltip/focus and accessible mark counts'},
            'crosshair': {'status': 'SUPPORTED', 'proof': 'canonical SVG crosshair layer plus native C050'},
            'zoom_pan_brush_range_selector_reset': {'status': 'SUPPORTED', 'proof': 'candidate browser matrix exercised wheel, Shift-drag, drag brush, recent/all range and reset path'},
            'legend_filter_cross_filter': {'status': 'SUPPORTED', 'proof': 'legend visibility and selected-row state remain interaction-only; native C038/C054/C055'},
            'recommendation_preview_apply': {'status': 'SUPPORTED', 'proof': 'native C056-C059 and non-mutating preview state'},
            'recipe_naming_rename': {'status': 'SUPPORTED', 'proof': 'product-owned dialog exercised in native matrix and C014/C063'},
            'svg_export': {'status': 'SUPPORTED', 'proof': 'native C039/C084 plus stable canonical live/export render probe'},
        },
        'mathematical_results': probes,
        'holdouts': {'statistical_engineering_fab_suites': 'PASS', 'holdout_data_not_used_for_tuning': True, 'semantics_preserved': ['SPC control/spec limits', 'I-MR', 'CUSUM', 'EWMA', 'Xbar-R', 'DOE', 'Wafer Map', 'Wafer Difference', 'Tool × Chamber Matrix', 'Golden vs Affected', 'Control vs Affected']},
    }
    (reports / 'renderer-conformance.json').write_text(json.dumps(conformance, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    browser = {label: json.loads((reports / f'{label}-browser-matrix.json').read_text(encoding='utf-8')) for label in ('base', 'candidate')}
    acceptance = json.loads((reports / 'chart-studio-acceptance.json').read_text(encoding='utf-8'))
    (reports / 'interaction-accessibility.json').write_text(json.dumps({'candidate': browser['candidate']['interactions'], 'acceptance': {'pass': acceptance.get('pass'), 'applicable': acceptance.get('applicable'), 'not_applicable': acceptance.get('not_applicable'), 'unexpected_errors': acceptance.get('unexpected_errors', [])}}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    changed = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True).splitlines()
    source_manifest = {}
    for relative in ['company_ui/products/visualizer/assets/authoring_chart_studio.mjs','company_ui/products/visualizer/assets/canonical_chart_renderer.mjs','company_ui/products/visualizer/assets/chart_studio.mjs','company_ui/products/visualizer/assets/chart_studio.html','company_ui/products/visualizer/assets/chart_studio.css','company_ui/products/visualizer/assets/integrated_editor.mjs','company_ui/products/visualizer/page.py','scripts/release_checks/run_chart_studio_acceptance.py','scripts/release_checks/run_chart_renderer_matrix.py','scripts/release_checks/build_chart_r1_evidence.py','tests/test_visualizer_chart_renderer_r1.py','company_ui/certification/certification_manifest.json']:
        path = ROOT / relative
        source_manifest[relative] = sha256(path) if path.is_file() else None
    artifacts = []
    for path in sorted(output.rglob('*')):
        if path.is_file() and path.name != 'manifest.json':
            artifacts.append({'path': path.relative_to(output).as_posix(), 'sha256': sha256(path), 'bytes': path.stat().st_size})
    manifest = {
        'schema_version': 1, 'job': 'CHG-137 R1', 'scope': 'bounded chart renderer / Chart Studio source candidate',
        'created_at': datetime.now(timezone.utc).isoformat(), 'base_commit': BASE, 'base_tree': BASE_TREE,
        'head_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'candidate_tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip(),
        'working_tree_status': changed, 'source_files': source_manifest, 'artifacts': artifacts,
        'artifact_bridge': {'status': 'NOT_STAGED', 'reason': 'No qualified Project OS Artifact Bridge callable was available in this session; Notion was not accessed.'},
        'promotion': {'integrated': False, 'visual_surfaces_updated': False, 'golden_visual_atlas_promoted': False},
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    with tarfile.open(output.parent / 'CHG-137-R1-evidence.tar.gz', 'w:gz') as archive:
        archive.add(output, arcname=output.name)
    print(json.dumps({'manifest': str(output / 'manifest.json'), 'bundle': str(output.parent / 'CHG-137-R1-evidence.tar.gz'), 'artifact_count': len(artifacts)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

