from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def node_json(source: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_promoted_fab_visuals_are_data_backed_and_value_level():
    payload = node_json(
        r'''
import {PRODUCTION_LIBRARY_COUNT, isProductionElement} from './company_ui/products/visualizer/assets/production_library.mjs';
import {chartModelFromEntry, recommendationsFor, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
import {executeRecipeSemantics} from './company_ui/products/visualizer/assets/analysis_semantics.mjs';

const n=(id,name,t='number',tags=[])=>({id,name,type:t,semantic_tags:tags});
const c=(id,name,tags=[])=>({id,name,type:'categorical',semantic_tags:tags});
const render=(element,engine,dataset,mapping)=>renderChartSvg(chartModelFromEntry({element,engine,mapping},dataset),{width:820,height:480});

const waferSource={id:'wafer',revision:1,fields:[n('x','Die X','number',['die_x']),n('y','Die Y','number',['die_y']),n('r','Reference','number',['reference_value']),n('a','Affected','number',['affected_value'])],rows:[[1,1,10,11],[2,1,10,15],[3,1,10,9]]};
const wafer=executeRecipeSemantics('wafer-difference',waferSource,{die_x:'x',die_y:'y',reference_value:'r',affected_value:'a'});
const waferSvg=render('Wafer Difference Map','WaferFabEngine',wafer.dataset,wafer.mapping);
const changedWafer={...wafer.dataset,rows:wafer.dataset.rows.map(row=>row.slice())};changedWafer.rows[1][3]=25;
const changedWaferSvg=render('Wafer Difference Map','WaferFabEngine',changedWafer,wafer.mapping);

const matrixSource={id:'matrix',revision:1,fields:[c('tool','Tool',['tool']),c('chamber','Chamber',['chamber']),n('v','Measurement','number',['value'])],rows:[['ETCH-01','A',10],['ETCH-01','A',14],['ETCH-01','B',20],['ETCH-02','A',8]]};
const matrix=executeRecipeSemantics('tool-chamber-matching',matrixSource,{tool:'tool',chamber:'chamber',value:'v'});
const matrixSvg=render('Tool × Chamber Matrix','WaferFabEngine',matrix.dataset,matrix.mapping);
const directRecommendations=recommendationsFor(chartModelFromEntry({element:'Tool × Chamber Matrix',engine:'WaferFabEngine',mapping:{tool:'tool',chamber:'chamber',value:'v'}},matrixSource)).map(item=>item.type);

const profileSource={id:'profile',revision:1,fields:[n('x','Position'),n('r','Reference'),n('a','Affected')],rows:[[1,10,11],[2,15,9],[3,12,14]]};
const profile=executeRecipeSemantics('golden-affected',profileSource,{x:'x',reference_value:'r',affected_value:'a'});
const profileSvg=render('Golden vs Affected Profile','WaferFabEngine',profile.dataset,profile.mapping);

const distSource={id:'dist',revision:1,fields:[c('cohort','Cohort',['cohort']),n('v','Measurement','number',['value'])],rows:[['Control',10],['Control',12],['Affected',30],['Affected',34]]};
const distribution=executeRecipeSemantics('distribution-comparison',distSource,{cohort:'cohort',value:'v'});
const distributionSvg=render('Control vs Affected Distribution','WaferFabEngine',distribution.dataset,distribution.mapping);
console.log(JSON.stringify({
  count:PRODUCTION_LIBRARY_COUNT,
  promoted:['Wafer Difference Map','Tool × Chamber Matrix','Golden vs Affected Profile','Control vs Affected Distribution'].map(element=>isProductionElement('WaferFabEngine',element)),
  wafer:{rows:wafer.rows,svg:waferSvg,changed:waferSvg!==changedWaferSvg},
  matrix:{rows:matrix.rows,svg:matrixSvg},
  directRecommendations,
  profile:{rows:profile.rows,svg:profileSvg},
  distribution:{summary:distribution.summary,svg:distributionSvg},
}));
'''
    )

    assert payload["count"] == 49
    assert all(payload["promoted"])
    assert [row["delta"] for row in payload["wafer"]["rows"]] == [1, 5, -1]
    assert "Reference 10" in payload["wafer"]["svg"]
    assert "Affected 15" in payload["wafer"]["svg"]
    assert "Delta 5" in payload["wafer"]["svg"]
    assert "Signed delta = Affected − Reference" in payload["wafer"]["svg"]
    assert payload["wafer"]["changed"] is True

    matrix_rows = {(row["tool"], row["chamber"]): row["value"] for row in payload["matrix"]["rows"]}
    assert matrix_rows[("ETCH-01", "A")] == 12
    assert "ETCH-01 · A · mean measurement 12" in payload["matrix"]["svg"]
    assert "ETCH-02 · B · missing" in payload["matrix"]["svg"]
    assert 'data-filter-fields="__tool,__chamber"' in payload["matrix"]["svg"]
    assert payload["directRecommendations"][0] == "Tool × Chamber Matrix"

    assert [row["cohort"] for row in payload["profile"]["rows"]] == ["Golden", "Affected", "Golden", "Affected", "Golden", "Affected"]
    assert "1 · 10" in payload["profile"]["svg"]
    assert "1 · 11" in payload["profile"]["svg"]
    assert "2 · 15" in payload["profile"]["svg"]
    assert "2 · 9" in payload["profile"]["svg"]

    assert payload["distribution"]["summary"]["cohorts"] == ["Affected", "Control"]
    assert "Control" in payload["distribution"]["svg"]
    assert "Affected" in payload["distribution"]["svg"]
    assert "n=2" in payload["distribution"]["svg"]


def test_dedicated_visuals_have_explicit_empty_states_and_no_non_finite_geometry():
    payload = node_json(
        r'''
import {chartModelFromEntry, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const empty={id:'empty',revision:1,fields:[],rows:[]};
const output=['Wafer Difference Map','Tool × Chamber Matrix','Golden vs Affected Profile','Control vs Affected Distribution'].map(element=>{const model=chartModelFromEntry({element,engine:'WaferFabEngine'},empty);const svg=renderChartSvg(model);return {element,hasSvg:svg.includes('<svg'),hasError:/NaN|Infinity/.test(svg),hasExplanation:/Map |No |Both /.test(svg)};});
console.log(JSON.stringify(output));
'''
    )
    assert all(item["hasSvg"] and not item["hasError"] and item["hasExplanation"] for item in payload)
