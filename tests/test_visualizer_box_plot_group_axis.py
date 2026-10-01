"""Box plots compare groups; observation values must not form an X scale."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('groups', [['Reference', 'Affected'], ['Only cohort'], [0, 7]])
def test_box_plot_uses_one_ordinal_axis_for_groups_even_with_legacy_numeric_x(groups):
    script = r'''
    import {chartModelFromEntry, chartRenderPlan, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
    const groups=JSON.parse(process.argv[1]);
    const dataset={id:'population',fields:[{id:'group',name:'Population',type:typeof groups[0]==='number'?'integer':'categorical'},{id:'reading',name:'Yield',type:'number'}],rows:groups.flatMap((group,index)=>[93.8,94.1,94.6].map(value=>[group,value+index*4]))};
    const entry={element:'Box Plot',mapping:{category:'group',value:'reading',x:'reading',y:'reading'},dataset};
    const model=chartModelFromEntry(entry,dataset),before=JSON.stringify(model);
    const plan=chartRenderPlan(model,{width:680,height:330});
    const svg=renderChartSvg(model,{width:680,height:330});
    const axisLabels=[...svg.matchAll(/class="cs-axis-label"[^>]*data-full-value="([^"]*)"/g)].map(match=>match[1]);
    console.log(JSON.stringify({labels:axisLabels,numeric:plan.xNumeric,groupCenters:[...plan.box.groups.keys()].map((group,index)=>plan.xAt(index,'category')),quartiles:[...plan.box.groups.values()],unchanged:before===JSON.stringify(model),unsafe:/NaN|Infinity/.test(svg)}));
    '''
    result = subprocess.run(['node', '--input-type=module', '--eval', script, json.dumps(groups)], cwd=ROOT, capture_output=True, text=True, check=True, timeout=30)
    facts = json.loads(result.stdout)
    assert facts['labels'] == [str(group) for group in groups]
    assert facts['numeric'] is False
    assert facts['quartiles'] == [[93.8 + index * 4, 94.1 + index * 4, 94.6 + index * 4] for index in range(len(groups))]
    assert facts['groupCenters'] == sorted(set(facts['groupCenters']))
    assert facts['unchanged'] and not facts['unsafe']
