"""Focused contract tests for the local Diagram Studio model."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = "./company_ui/products/visualizer/assets/authoring_diagram_studio.mjs"


def run_model_probe() -> dict:
    script = f"""
import * as d from {json.dumps(MODULE)};
const legacy = d.diagramFromEntry({{nodes:['Source','Inspect','Release'], edges:[['Source','Inspect'],['Inspect','Release']], direction:'down', edge_label:'handoff'}});
const route = d.routeEdge(legacy, legacy.edges[0]);
const routed = d.autoLayout(legacy, {{direction:'right'}});
const overlap = routed.nodes.some((a, i) => routed.nodes.slice(i + 1).some(b => d.rectsOverlap(d.nodeRect(a), d.nodeRect(b))));
const obstacle = d.normalizeDiagram({{nodes:[
  {{id:'a',label:'A',x:20,y:120,width:100,height:60}},
  {{id:'b',label:'B',x:250,y:120,width:100,height:60}},
  {{id:'c',label:'C',x:500,y:120,width:100,height:60}}
], edges:[{{id:'ab',source:'a',target:'c',routing:'orthogonal'}}]}});
const obstacleRoute = d.routeEdge(obstacle, obstacle.edges[0]);
const hitsObstacle = obstacleRoute.slice(1).some((point, i) => d.rectsOverlap(
  {{x:Math.min(obstacleRoute[i].x, point.x),y:Math.min(obstacleRoute[i].y, point.y),w:Math.abs(point.x-obstacleRoute[i].x)||1,h:Math.abs(point.y-obstacleRoute[i].y)||1}},
  d.nodeRect(obstacle.nodes[1])
));
let large = d.normalizeDiagram({{nodes:Array.from({{length:100}}, (_, i) => ({{id:`n${{i}}`,label:`N${{i}}`}})), edges:Array.from({{length:150}}, (_, i) => ({{source:`n${{i % 99}}`,target:`n${{(i + 1 + (i % 3)) % 100}}`}}))}});
large.edges = large.edges.filter(edge => edge.source !== edge.target);
const clean = d.cleanDiagram(large, {{direction:'right'}});
const cleanOverlap = clean.nodes.some((a, i) => clean.nodes.slice(i + 1).some(b => d.rectsOverlap(d.nodeRect(a), d.nodeRect(b))));
const steps = d.pasteProcessSteps(d.normalizeDiagram({{}}), 'Detect\\nAnalyze\\nVerify\\nRelease');
const graph = d.pasteSourceTargetTable(d.normalizeDiagram({{}}), 'Source\\tTarget\\tLabel\\nTool\\tChamber\\tfeeds\\nChamber\\tInspection\\tchecks');
let grouped = d.groupNodes(steps.diagram, steps.ids.slice(0, 2), 'Control path').diagram;
const groupId = grouped.groups[0].id;
grouped = d.moveContainer(grouped, groupId, {{x:12,y:8}});
const layerAdded = d.addLayer(grouped, 'Analysis');
const layerCopy = d.duplicateLayer(layerAdded.diagram, layerAdded.layer.id).diagram;
const laneAdded = d.addLane(layerCopy, {{label:'Fab', orientation:'horizontal'}});
const laneMoved = d.moveNodesToLane(laneAdded.diagram, [steps.ids[0]], laneAdded.lane.id);
const subflow = d.createSubflow(laneMoved, steps.ids.slice(0, 3), 'Control path');
const reinserted = d.insertSubflow(laneMoved, subflow, {{x:800,y:80}});
console.log(JSON.stringify({{schema:legacy.schema,version:legacy.version,legacyDirection:legacy.layout.direction,legacyLabel:legacy.edges[0].labels[0].text,routePoints:route.length,overlap,hitsObstacle,cleanOverlap,shapeCount:d.SHAPE_CATALOG.length,processNodes:steps.ids.length,processEdges:steps.diagram.edges.length,graphNodes:graph.diagram.nodes.length,graphLabels:graph.diagram.edges.map(edge=>edge.labels[0]?.text),groupMoved:grouped.groups[0].x===48,layers:layerCopy.layers.length,lanes:laneMoved.swimlanes.length,reinserted:reinserted.ids.length}}));
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_versioned_diagram_model_preserves_legacy_contract_and_geometry() -> None:
    result = run_model_probe()
    assert result["schema"] == "visembler.diagram.studio"
    assert result["version"] == 1
    assert result["legacyDirection"] == "down"
    assert result["legacyLabel"] == "handoff"
    assert result["routePoints"] >= 2
    assert not result["overlap"]
    assert not result["hitsObstacle"]
    assert not result["cleanOverlap"]
    assert result["shapeCount"] >= 20
    assert result["processNodes"] == 4
    assert result["processEdges"] == 3
    assert result["graphNodes"] == 3
    assert result["graphLabels"] == ["feeds", "checks"]
    assert result["groupMoved"]
    assert result["layers"] == 3
    assert result["lanes"] == 1
    assert result["reinserted"] == 3

