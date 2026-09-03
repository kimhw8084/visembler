from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def node_json(source: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_wave5_builds_multi_selection_payload_with_complete_groups_and_datasets() -> None:
    result = node_json(
        r"""
import {buildCompositionClipboard}
from './company_ui/products/visualizer/assets/authoring_clipboard.mjs';
const model={
  mode:'guided',
  items:[
    {id:'c1',title:'A',groupId:'g1',dataset_id:'ds1'},
    {id:'c2',title:'B',groupId:'g1',dataset_id:'ds1'},
    {id:'c3',title:'C',groupId:'g2'},
    {id:'c4',title:'D',groupId:'g2'},
  ],
  groups:{
    g1:{id:'g1',items:['c1','c2'],layout:{kind:'row'}},
    g2:{id:'g2',items:['c3','c4'],layout:{kind:'row'}},
  },
  datasets:[{
    id:'ds1',name:'Typed',revision:7,
    fields:[{id:'v',name:'Value',type:'string'}],
    rows:[[0,'0',null,'']],
  }],
};
console.log(JSON.stringify(buildCompositionClipboard(
  model,['c1','c2','c3'],
  {rects:{c1:{x:10,y:20,w:100,h:80},c2:{x:130,y:20,w:100,h:80},c3:{x:250,y:20,w:100,h:80}}}
)));
"""
    )
    assert result["kind"] == "composition"
    assert [item["id"] for item in result["items"]] == ["c1", "c2", "c3"]
    assert [group["id"] for group in result["groups"]] == ["g1"]
    assert [dataset["id"] for dataset in result["datasets"]] == ["ds1"]
    assert result["datasets"][0]["rows"][0] == [0, "0", None, ""]
    assert result["items"][0]["_clipboard_rect"] == {"x": 10, "y": 20, "w": 100, "h": 80}


def test_wave5_paste_remaps_items_groups_and_datasets_independently() -> None:
    result = node_json(
        r"""
import {pasteCompositionPlan}
from './company_ui/products/visualizer/assets/authoring_clipboard.mjs';
const model={
  mode:'free',nextId:10,
  items:[{id:'c1',z:4}],
  groups:{},
  datasets:[{id:'dataset-paste-10-1',name:'Existing',rows:[]}],
};
const payload={
  kind:'composition',version:2,source_mode:'guided',
  items:[
    {id:'a',title:'Metric',groupId:'g',dataset_id:'source-ds',_clipboard_rect:{x:20,y:30,w:100,h:80}},
    {id:'b',title:'Chart',groupId:'g',dataset_id:'source-ds',_clipboard_rect:{x:140,y:30,w:160,h:100}},
  ],
  groups:[{id:'g',items:['a','b'],layout:{kind:'row',gap:14}}],
  datasets:[{
    id:'source-ds',name:'Typed',revision:9,
    fields:[{id:'v',name:'Value',type:'string'}],
    rows:[[0,'0',null,'']],
  }],
};
console.log(JSON.stringify(pasteCompositionPlan(
  model,payload,{mode:'free',canvasWidth:1000,canvasHeight:800,inset:0,offset:24}
)));
"""
    )
    assert result["newIds"] == ["c10", "c11"]
    assert result["nextId"] == 12
    added = [op["item"] for op in result["ops"] if op["op"] == "item.add"]
    assert [item["x"] for item in added] == [44, 164]
    assert [item["y"] for item in added] == [54, 54]
    assert all(item["groupId"] == "g-paste-10-1" for item in added)
    assert all(item["dataset_id"] == "dataset-paste-10-1-2" for item in added)

    group = next(op for op in result["ops"] if op["op"] == "group.set")
    assert group["value"]["items"] == ["c10", "c11"]

    patch = next(op["patch"] for op in result["ops"] if op["op"] == "model.patch")
    cloned = patch["datasets"][-1]
    assert cloned["id"] == "dataset-paste-10-1-2"
    assert cloned["rows"][0] == [0, "0", None, ""]


def test_wave5_partial_group_is_detached_on_paste() -> None:
    result = node_json(
        r"""
import {pasteCompositionPlan}
from './company_ui/products/visualizer/assets/authoring_clipboard.mjs';
const payload={
  kind:'composition',
  items:[
    {id:'a',title:'A',groupId:'missing-group',_clipboard_rect:{x:0,y:0,w:100,h:80}},
    {id:'b',title:'B',groupId:null,_clipboard_rect:{x:120,y:0,w:100,h:80}},
  ],
  groups:[],
  datasets:[],
};
console.log(JSON.stringify(pasteCompositionPlan(
  {mode:'guided',nextId:4,items:[],groups:{},datasets:[]},
  payload,{mode:'guided',canvasWidth:500,canvasHeight:300,inset:14}
)));
"""
    )
    added = [op["item"] for op in result["ops"] if op["op"] == "item.add"]
    assert all(item["groupId"] is None for item in added)


def test_wave5_editor_keeps_single_visual_semantic_modes_and_adds_composition_branch() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "buildCompositionClipboard" in editor
    assert "pasteCompositionPlan" in editor
    assert "payload?.kind==='composition'" in editor
    assert "kind==='dataset_data'" in editor
    assert "mode==='mapping'" in editor
    assert "mode==='style'" in editor
    assert "mode==='append-data'" in editor


def test_wave5_standard_copy_cut_paste_shortcuts_are_wired_without_data_grid_conflict() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "function cutSemanticSelection()" in editor
    assert "function pasteSemanticClipboard()" in editor
    assert "e.key.toLowerCase()==='x'&&!editing" in editor
    assert "copySemanticSelection(" in editor
    assert "pasteSemanticClipboard(" in editor
    assert "if(editing)return;" in editor


def test_wave5_commands_and_help_surface_clipboard_workflow() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "Copy selection" in editor
    assert "Cut selection" in editor
    assert "Paste clipboard" in editor
    assert "Copy selected visual or composition" in editor
    assert "Cut unlocked selection" in editor


def test_wave5_clipboard_asset_is_fingerprinted() -> None:
    page = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    assert "'authoring_clipboard.mjs'" in page
