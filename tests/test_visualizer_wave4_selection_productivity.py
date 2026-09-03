from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"

def node_json(source: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    return json.loads(result.stdout)

def test_wave4_multi_duplicate_preserves_complete_group_structure() -> None:
    result = node_json(r'''
import {duplicateSelectionPlan} from './company_ui/products/visualizer/assets/authoring_selection.mjs';
const model={
  mode:'guided',nextId:20,
  items:[
    {id:'c1',title:'A',x:10,y:20,w:100,h:80,z:1,order:0,groupId:'g1'},
    {id:'c2',title:'B',x:150,y:20,w:100,h:80,z:2,order:1,groupId:'g1'},
    {id:'c3',title:'C',x:300,y:20,w:100,h:80,z:3,order:2,groupId:null},
  ],
  groups:{g1:{id:'g1',items:['c1','c2'],layout:{kind:'row',gap:14}}},
};
console.log(JSON.stringify(duplicateSelectionPlan(
  model,['c1','c2'],{mode:'guided',canvasWidth:1000,canvasHeight:800}
)));
''')
    assert result["newIds"] == ["c20", "c21"]
    added = [op["item"] for op in result["ops"] if op["op"] == "item.add"]
    assert [x["x"] for x in added] == [34, 174]
    assert [x["y"] for x in added] == [44, 44]
    assert all(x["groupId"] == "g-copy-20-1" for x in added)
    group = next(op for op in result["ops"] if op["op"] == "group.set")
    assert group["value"]["items"] == ["c20", "c21"]
    assert group["value"]["layout"] == {"kind": "row", "gap": 14}

def test_wave4_partial_group_duplicate_detaches_and_clamps() -> None:
    result = node_json(r'''
import {duplicateSelectionPlan} from './company_ui/products/visualizer/assets/authoring_selection.mjs';
const model={
  mode:'free',nextId:5,
  items:[
    {id:'c1',title:'A',x:980,y:780,w:100,h:80,z:1,order:0,groupId:'g1'},
    {id:'c2',title:'B',x:0,y:0,w:100,h:80,z:2,order:1,groupId:'g1'},
  ],
  groups:{g1:{id:'g1',items:['c1','c2'],layout:{kind:'row'}}},
};
console.log(JSON.stringify(duplicateSelectionPlan(
  model,['c1'],{mode:'free',canvasWidth:1000,canvasHeight:800}
)));
''')
    added = next(op["item"] for op in result["ops"] if op["op"] == "item.add")
    assert added["groupId"] is None
    assert added["x"] == 900
    assert added["y"] == 720
    assert not any(op["op"] == "group.set" for op in result["ops"])

def test_wave4_editor_surfaces_selection_productivity() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "duplicateSelectionPlan" in editor
    assert "function duplicateSelected()" in editor
    assert "function selectAllComponents()" in editor
    assert "value==='duplicate'" in editor
    assert "value==='delete'" in editor
    assert "Duplicate selection" in editor
    assert "Select all elements" in editor
    assert "Delete selection" in editor
    assert editor.count('data-inspector="duplicate"') >= 2
    assert editor.count('data-inspector="delete"') >= 2
    assert "Duplicate · Cmd/Ctrl+D" in editor

def test_wave4_selection_asset_is_fingerprinted() -> None:
    page = (ROOT / "company_ui" / "products" / "visualizer" / "page.py").read_text(encoding="utf-8")
    assert "'authoring_selection.mjs'" in page
