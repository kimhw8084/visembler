from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def _benchmark() -> list[dict[str, float | int]]:
    script="""
import { intakeText } from './company_ui/products/visualizer/assets/authoring_data.mjs';
import { applyRecipe } from './company_ui/products/visualizer/assets/authoring_transforms.mjs';
import { PERFORMANCE_LIMITS, sampledRows } from './company_ui/products/visualizer/assets/authoring_performance.mjs';
for (const count of [10000,50000,100000]) {
  const text=['Lot\\tYield\\tTimestamp'];
  for(let i=0;i<count;i+=1)text.push(`L${String(i).padStart(6,'0')}\\t${98+(i%25)/100}\\t2026-01-${String((i%28)+1).padStart(2,'0')}`);
  const started=performance.now(), intake=intakeText(text.join('\\n')), intakeMs=performance.now()-started;
  const dataset={id:'d',fields:intake.fields,rows:intake.rows}; const before=dataset.rows[0].length;
  const transformed=applyRecipe(dataset,{steps:[{type:'derive',source_field:intake.fields[1].id,multiplier:0,offset:0}]});
  if(dataset.rows[0].length!==before||transformed.rows[0][before]!==0)throw new Error('transform mutated source or lost zero');
  const preview=sampledRows(dataset.rows,PERFORMANCE_LIMITS.chartRows);
  console.log(JSON.stringify({count,intake_ms:intakeMs,rows:intake.rows.length,profile_warning:intake.warnings.some(w=>w.code==='profile_sampled'),preview_rows:preview.length,first:preview[0][0],last:preview.at(-1)[0]}));
}
"""
    result=subprocess.run(['node','--input-type=module','--eval',script],cwd=ROOT,text=True,capture_output=True,check=True,timeout=20)
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def test_large_data_intake_and_preview_benchmark_contract():
    measurements=_benchmark()
    assert [entry['count'] for entry in measurements]==[10_000,50_000,100_000]
    for entry in measurements:
        assert entry['rows']==entry['count']
        assert entry['preview_rows']<=1200
        assert entry['first']=='L000000' and entry['last']==f"L{entry['count']-1:06d}"
        assert entry['intake_ms']<5_000
    assert not measurements[0]['profile_warning']
    assert measurements[1]['profile_warning'] and measurements[2]['profile_warning']


def test_performance_contract_is_wired_into_authoring_paths():
    editor=(ROOT/'company_ui/products/visualizer/assets/integrated_editor.mjs').read_text(encoding='utf-8')
    page=(ROOT/'company_ui/products/visualizer/page.py').read_text(encoding='utf-8')
    assert 'PERFORMANCE_LIMITS.chartRows' in editor
    assert 'resolvedDataCache' in editor
    assert 'authoring_performance.mjs' in page
