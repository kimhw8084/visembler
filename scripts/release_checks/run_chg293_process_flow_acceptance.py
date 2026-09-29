#!/usr/bin/env python3
"""Native browser geometry and whole-report acceptance for CHG-293 R2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from editor_host import NativeHost
from native_common import BrowserEvents, browser_kwargs, ready, write_json

BASE_SHA = "28d47acbaab8b493044120f6be4c32a225de4143"
BASE_TREE = "6b535f84478f0e8394a06614961e8faa0df54a75"
WORK_BRANCH = "fix/visembler-chg293-ci-hermetic-r2"
FIXTURE = "tests/fixtures/chg206/whole_report_models.json"
SOURCE = "company_ui/products/visualizer/assets/authoring_diagram_studio.mjs"

R6_LIKE = [
    "Map wafer cluster",
    "Compare matched lot",
    "Check CF-4 pressure",
    "Confirm containment",
]
FOUR_STAGE_HOLDOUT = [
    "Review matched-lot distributions",
    "Isolate chamber pressure excursion",
    "Verify sensor calibration with controls",
    "Authorize release after Quality confirmation",
]
FIVE_STAGE_HOLDOUT = [
    "Map the affected wafer population",
    "Compare matched reference lots",
    "Trace the chamber pressure excursion",
    "Verify corrective maintenance results",
    "Release only after Quality review",
]
SIX_STAGE_HOLDOUT = [
    "Detect the localized yield shift",
    "Map affected die and wafer regions",
    "Compare matched-lot process signals",
    "Check the chamber pressure trace",
    "Verify the sensor against controls",
    "Confirm containment and release status",
]
WIDTHS = (1440, 520, 390, 361, 360, 320)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def optional_ref(ref: str) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def base_ancestry(head: str, *, strict: bool) -> bool | None:
    base_commit = subprocess.run(
        ["git", "cat-file", "-e", f"{BASE_SHA}^{{commit}}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if base_commit.returncode != 0:
        if strict:
            raise ValueError("Candidate/reproduction qualification requires the exact base commit object.")
        return None
    if git("rev-parse", f"{BASE_SHA}^{{tree}}") != BASE_TREE:
        raise ValueError("The exact CHG-293 base commit has an unexpected tree.")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_SHA, head],
        cwd=ROOT,
        check=False,
    )
    if result.returncode not in (0, 1):
        if strict:
            raise ValueError("Candidate/reproduction base ancestry could not be evaluated.")
        return None
    return result.returncode == 0


def flow_entry(model: dict) -> dict:
    return next(item for item in model["items"] if item.get("element") == "Process Flow")


def set_flow(model: dict, labels: list[str], *, secondary: bool = False, edge_label: str = "") -> dict:
    result = copy.deepcopy(model)
    flow = flow_entry(result)
    flow["nodes"] = labels
    flow["edges"] = [[labels[index], labels[index + 1]] for index in range(len(labels) - 1)]
    flow["diagram"] = {
        "schema": "visembler.diagram.studio",
        "version": 1,
        "nodes": [
            {
                "id": f"chg293-node-{index + 1}",
                "shape": "process",
                "label": label,
                "secondary": f"Evidence checkpoint {index + 1}" if secondary else "",
                "x": 64 + index * 236,
                "y": 64,
            }
            for index, label in enumerate(labels)
        ],
        "edges": [
            {
                "id": f"chg293-edge-{index + 1}",
                "source": f"chg293-node-{index + 1}",
                "target": f"chg293-node-{index + 2}",
                "labels": ([{"id": f"chg293-edge-label-{index + 1}", "text": edge_label, "position": "center", "offset": 0}]
                           if edge_label and index == 1 else []),
            }
            for index in range(len(labels) - 1)
        ],
        "groups": [],
        "swimlanes": [],
        "layers": [{"id": "base", "name": "Main diagram", "visible": True, "order": 0}],
        "layout": {"direction": "right", "mode": "horizontal", "preservePinned": True},
    }
    return result


def geometry_facts(page, flow_id: str) -> dict:
    return page.evaluate(
        r"""(flowId)=>{
          const component=document.querySelector(`.component[data-id="${CSS.escape(flowId)}"]`);
          const candidates=[...(component?.querySelectorAll('.diagram-responsive-reading>svg')||[])];
          const svg=candidates.find(el=>getComputedStyle(el).display!=='none');
          if(!svg)return {error:'No visible report-reading SVG',flowId};
          const reportModel=window.CompanyUIVisualizerBridge.state().model;
          const reportEntry=reportModel.items.find(item=>String(item.id)===String(flowId));
          const modelNodes=reportEntry?.diagram?.nodes||[],modelEdges=reportEntry?.diagram?.edges||[];
          const nodeOrder=new Map(modelNodes.map((node,index)=>[node.id,index])),edgeOrder=new Map(modelEdges.map((edge,index)=>[edge.id,index]));
          const matrix=svg.getScreenCTM(),view=svg.viewBox.baseVal;
          const transform=(x,y)=>{const p=new DOMPoint(x,y).matrixTransform(matrix);return {x:p.x,y:p.y};};
          const rectFromBBox=(el)=>{
            const b=el.getBBox(),points=[transform(b.x,b.y),transform(b.x+b.width,b.y+b.height)];
            return {left:Math.min(points[0].x,points[1].x),top:Math.min(points[0].y,points[1].y),right:Math.max(points[0].x,points[1].x),bottom:Math.max(points[0].y,points[1].y)};
          };
          const rectDistance=(a,b)=>{
            const dx=Math.max(a.left-b.right,b.left-a.right,0),dy=Math.max(a.top-b.bottom,b.top-a.bottom,0);
            return Math.hypot(dx,dy);
          };
          const pointRectDistance=(p,r)=>Math.hypot(Math.max(r.left-p.x,0,p.x-r.right),Math.max(r.top-p.y,0,p.y-r.bottom));
          const orient=(a,b,c)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
          const onSegment=(a,b,p)=>Math.min(a.x,b.x)-1e-6<=p.x&&p.x<=Math.max(a.x,b.x)+1e-6&&Math.min(a.y,b.y)-1e-6<=p.y&&p.y<=Math.max(a.y,b.y)+1e-6;
          const intersects=(a,b,c,d)=>{
            const ab1=orient(a,b,c),ab2=orient(a,b,d),cd1=orient(c,d,a),cd2=orient(c,d,b);
            return (ab1*ab2<0&&cd1*cd2<0)||(Math.abs(ab1)<1e-6&&onSegment(a,b,c))||(Math.abs(ab2)<1e-6&&onSegment(a,b,d))||(Math.abs(cd1)<1e-6&&onSegment(c,d,a))||(Math.abs(cd2)<1e-6&&onSegment(c,d,b));
          };
          const pointSegmentDistance=(p,a,b)=>{const dx=b.x-a.x,dy=b.y-a.y,t=Math.max(0,Math.min(1,((p.x-a.x)*dx+(p.y-a.y)*dy)/(dx*dx+dy*dy||1)));return Math.hypot(p.x-(a.x+t*dx),p.y-(a.y+t*dy));};
          const segmentDistance=(a,b,c,d)=>intersects(a,b,c,d)?0:Math.min(pointSegmentDistance(a,c,d),pointSegmentDistance(b,c,d),pointSegmentDistance(c,a,b),pointSegmentDistance(d,a,b));
          const rectEdges=r=>[[{x:r.left,y:r.top},{x:r.right,y:r.top}],[{x:r.right,y:r.top},{x:r.right,y:r.bottom}],[{x:r.right,y:r.bottom},{x:r.left,y:r.bottom}],[{x:r.left,y:r.bottom},{x:r.left,y:r.top}]];
          const segmentRectDistance=(a,b,r)=>{
            if(a.x>=r.left&&a.x<=r.right&&a.y>=r.top&&a.y<=r.bottom||b.x>=r.left&&b.x<=r.right&&b.y>=r.top&&b.y<=r.bottom)return 0;
            return Math.min(...rectEdges(r).map(([c,d])=>segmentDistance(a,b,c,d)));
          };
          const pointInPolygon=(p,poly)=>{let inside=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if(((a.y>p.y)!==(b.y>p.y))&&(p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x))inside=!inside;}return inside;};
          const polygonRectDistance=(poly,r)=>{
            const corners=[{x:r.left,y:r.top},{x:r.right,y:r.top},{x:r.right,y:r.bottom},{x:r.left,y:r.bottom}];
            if(poly.some(p=>p.x>=r.left&&p.x<=r.right&&p.y>=r.top&&p.y<=r.bottom)||corners.some(p=>pointInPolygon(p,poly)))return 0;
            let best=Infinity;for(let i=0;i<poly.length;i++)for(const [a,b] of rectEdges(r))best=Math.min(best,segmentDistance(poly[i],poly[(i+1)%poly.length],a,b));return best;
          };
          const nodeTextEls=[...new Set(svg.querySelectorAll('text[data-direct^="diagram-node:"],.diagram-reading-label,.diagram-reading-secondary,.diagram-node-secondary'))];
          const nodeTexts=nodeTextEls.map(el=>({id:el.closest('[data-diagram-node]')?.dataset.diagramNode,kind:el.classList.contains('diagram-reading-secondary')||el.classList.contains('diagram-node-secondary')?'secondary':'label',text:el.textContent.replace(/\s+/g,' ').trim(),rect:rectFromBBox(el)}));
          const edgeLabelTexts=[...svg.querySelectorAll('.diagram-reading-edge-label,.diagram-edge-label')].map(el=>({id:el.closest('[data-diagram-edge]')?.dataset.diagramEdge,text:el.textContent.replace(/\s+/g,' ').trim(),rect:rectFromBBox(el)}));
          const connectors=[...svg.querySelectorAll('[data-diagram-edge]')].map(edge=>{
            const path=edge.querySelector('path'),length=path.getTotalLength(),samples=Math.max(1,Math.ceil(length/1.5)),ctm=path.getScreenCTM(),points=[];
            for(let i=0;i<=samples;i++){const p=path.getPointAtLength(length*i/samples).matrixTransform(ctm);points.push({x:p.x,y:p.y});}
            const style=getComputedStyle(path),userStroke=parseFloat(style.strokeWidth)||1.8,scale=Math.sqrt(Math.abs(ctm.a*ctm.d-ctm.b*ctm.c)),halfStroke=userStroke*scale/2;
            let minimum=Infinity,nearest=null,intersections=0;
            for(let i=1;i<points.length;i++)for(const text of nodeTexts){const distance=Math.max(0,segmentRectDistance(points[i-1],points[i],text.rect)-halfStroke);if(distance<minimum){minimum=distance;nearest={nodeId:text.id,text:text.text,kind:text.kind};}if(distance<=0.2)intersections++;}
            const markerRef=path.getAttribute('marker-end'),markerId=markerRef?.match(/#([^\)]+)/)?.[1],marker=markerId&&svg.querySelector(`#${CSS.escape(markerId)}`);
            let arrowMinimum=Infinity,arrowNearest=null;
            if(marker&&points.length>1){
              const markerPath=marker.querySelector('path'),d=markerPath?.getAttribute('d')||'',vertices=[...d.matchAll(/[ML]\s*(-?[\d.]+)[ ,]+(-?[\d.]+)/g)].map(match=>({x:Number(match[1]),y:Number(match[2])}));
              const vb=(marker.getAttribute('viewBox')||'0 0 8 8').split(/[ ,]+/).map(Number),refX=Number(marker.getAttribute('refX')||0),refY=Number(marker.getAttribute('refY')||0),markerWidth=Number(marker.getAttribute('markerWidth')||3),markerHeight=Number(marker.getAttribute('markerHeight')||3),factor=marker.getAttribute('markerUnits')==='userSpaceOnUse'?1:userStroke,kx=markerWidth/vb[2]*factor,ky=markerHeight/vb[3]*factor;
              const endLocal=path.getPointAtLength(length),beforeLocal=path.getPointAtLength(Math.max(0,length-0.5)),angle=Math.atan2(endLocal.y-beforeLocal.y,endLocal.x-beforeLocal.x),cos=Math.cos(angle),sin=Math.sin(angle);
              const polygon=vertices.map(v=>{const x=(v.x-refX)*kx,y=(v.y-refY)*ky,p=new DOMPoint(endLocal.x+x*cos-y*sin,endLocal.y+x*sin+y*cos);return p.matrixTransform(ctm);});
              for(const text of nodeTexts){const distance=polygonRectDistance(polygon,text.rect);if(distance<arrowMinimum){arrowMinimum=distance;arrowNearest={nodeId:text.id,text:text.text,kind:text.kind};}if(distance<=0.2)intersections++;}
            }
            const semanticEdge=modelEdges.find(item=>item.id===edge.dataset.diagramEdge);
            return {id:edge.dataset.diagramEdge,order:Number.isFinite(Number(edge.dataset.edgeOrder))?Number(edge.dataset.edgeOrder):(edgeOrder.get(edge.dataset.diagramEdge)??0),source:edge.dataset.sourceId||semanticEdge?.source||null,target:edge.dataset.targetId||semanticEdge?.target||null,path:path.getAttribute('d'),shaft_clearance_px:Number.isFinite(minimum)?Number(minimum.toFixed(2)):null,shaft_nearest:nearest,arrowhead_clearance_px:Number.isFinite(arrowMinimum)?Number(arrowMinimum.toFixed(2)):null,arrowhead_nearest:arrowNearest,text_intersections:intersections};
          });
          let edgeLabelClearance=Infinity,edgeLabelPair=null;
          for(const label of edgeLabelTexts)for(const text of nodeTexts){const distance=rectDistance(label.rect,text.rect);if(distance<edgeLabelClearance){edgeLabelClearance=distance;edgeLabelPair={edgeId:label.id,edgeText:label.text,nodeId:text.id,nodeText:text.text};}}
          const svgRect=svg.getBoundingClientRect(),componentRect=component.getBoundingClientRect(),union=rect=>({x:rect.left,y:rect.top,width:rect.right-rect.left,height:rect.bottom-rect.top});
          return {flowId,projection:svg.classList.contains('diagram-wide-reading')?'wide':svg.classList.contains('diagram-narrow-reading')?'narrow':`medium-${svg.dataset.readingColumns}-column`,readingColumns:Number(svg.dataset.readingColumns||0),readingDirection:svg.dataset.readingDirection||null,canonicalDirection:svg.dataset.canonicalDirection||svg.dataset.direction||null,viewBox:{width:view.width,height:view.height},renderedScale:Number((svgRect.width/view.width).toFixed(4)),clearancePolicy:{minimumCssPx:Number(svg.dataset.readingClearancePx||0),protectedPadding:Number(svg.dataset.readingProtectedPadding||0),protectedPaddingY:Number(svg.dataset.readingProtectedPaddingY||svg.dataset.readingProtectedPadding||0),markerEnvelope:Number(svg.dataset.readingMarkerEnvelope||0),markerForwardEnvelope:Number(svg.dataset.readingMarkerForwardEnvelope||0),minimumScale:Number(svg.dataset.readingMinimumScale||0)},svgRect:union({left:svgRect.left,top:svgRect.top,right:svgRect.right,bottom:svgRect.bottom}),componentRect:union({left:componentRect.left,top:componentRect.top,right:componentRect.right,bottom:componentRect.bottom}),nodes:[...svg.querySelectorAll('[data-diagram-node]')].map((node,index)=>({id:node.dataset.diagramNode,order:Number.isFinite(Number(node.dataset.nodeOrder))?Number(node.dataset.nodeOrder):(nodeOrder.get(node.dataset.diagramNode)??index),title:node.querySelector('title')?.textContent||`Step ${index+1}: ${modelNodes.find(item=>item.id===node.dataset.diagramNode)?.label||''}`,labels:nodeTexts.filter(text=>text.id===node.dataset.diagramNode),rect:union((()=>{const r=node.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom};})())})),edgeLabels:edgeLabelTexts,edgeLabelToNodeTextClearancePx:Number.isFinite(edgeLabelClearance)?Number(edgeLabelClearance.toFixed(2)):null,edgeLabelNearest:edgeLabelPair,connectors};
        }""",
        flow_id,
    )


def preview(page, host: NativeHost, report_id: str, width: int) -> dict:
    page.set_viewport_size({"width": width, "height": 900 if width < 800 else 1100})
    response = page.goto(f"{host.url}/visualizer?report={report_id}", wait_until="domcontentloaded")
    status = response.status if response else None
    assert status == 200, f"report route failed at {width}px (status={status}, url={page.url})"
    ready(page, require_settled=True)
    original_model = page.evaluate("()=>JSON.stringify(window.CompanyUIVisualizerBridge.state().model)")
    page.locator("#previewBtn").click()
    page.wait_for_function("()=>document.querySelector('.cui-visualizer-root')?.classList.contains('preview-mode')")
    page.wait_for_timeout(100)
    return {"model_snapshot": original_model, "geometry": geometry_facts(page, "c8")}


def run_acceptance(output: Path, *, phase: str = "local", candidate_sha: str = "", candidate_tree: str = "") -> dict:
    output = output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Acceptance output must be outside the source checkout.")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Acceptance output must be new or empty.")
    if phase not in ("local", "candidate", "reproduction"):
        raise ValueError(f"Unsupported acceptance phase: {phase}")
    head, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    main_snapshot = {
        "local_main": optional_ref("refs/heads/main"),
        "origin_main": optional_ref("refs/remotes/origin/main"),
    }
    strict_lineage = phase in ("candidate", "reproduction")
    if strict_lineage:
        unavailable = [name for name, value in main_snapshot.items() if value is None]
        if unavailable:
            raise ValueError(f"{phase} acceptance requires provisioned main refs: {', '.join(unavailable)}")
        if main_snapshot["origin_main"] != BASE_SHA:
            raise ValueError("The provisioned origin/main ref has drifted from the exact CHG-293 base.")
    if phase == "reproduction" and (head != BASE_SHA or tree != BASE_TREE):
        raise ValueError("Pre-fix reproduction must run on the exact CHG-293 base commit and tree.")
    head_source = hashlib.sha256(subprocess.check_output(["git", "show", f"{head}:{SOURCE}"], cwd=ROOT)).hexdigest()
    if phase == "reproduction" and digest(ROOT / SOURCE) != head_source:
        raise ValueError("Pre-fix reproduction source differs from the exact base commit.")
    if phase == "candidate":
        if not candidate_sha or not candidate_tree or (head, tree) != (candidate_sha, candidate_tree):
            raise ValueError("Candidate acceptance must match its requested SHA and tree.")
        if git("branch", "--show-current") != WORK_BRANCH or git("status", "--porcelain"):
            raise ValueError("Candidate acceptance requires the exact clean CHG-293 work branch.")
    ancestry = base_ancestry(head, strict=strict_lineage)
    if strict_lineage and not ancestry:
        raise ValueError(f"{phase} acceptance requires the exact CHG-293 base to be an ancestor of HEAD.")
    output.mkdir(parents=True, exist_ok=True)
    fixture_path = ROOT / FIXTURE
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    source_rows = {row["key"]: row["model"] for row in fixture["reports"]}
    cases = {
        "r6-like": (R6_LIKE, False, ""),
        "four-stage-holdout": (FOUR_STAGE_HOLDOUT, False, ""),
        "five-stage-holdout": (FIVE_STAGE_HOLDOUT, False, ""),
        "six-stage-holdout": (SIX_STAGE_HOLDOUT, False, ""),
        "edge-secondary-labels": (R6_LIKE, True, "CF-4 excursion verified"),
    }
    receipt = {
        "schema": "visembler-chg293-process-flow-acceptance.v2",
        "phase": phase,
        "repository": "kimhw8084/visembler",
        "project": "visembler",
        "change": "CHG-293",
        "request": "CHG-293-r2",
        "operation": "FIX",
        "candidate_sha": candidate_sha or (head if phase != "reproduction" else ""),
        "candidate_tree": candidate_tree or (tree if phase != "reproduction" else ""),
        "base_sha": BASE_SHA,
        "base_tree": BASE_TREE,
        "base_is_ancestor": ancestry,
        "main_before": main_snapshot,
        "main_unchanged": None,
        "lineage": {
            "main_refs_before": {name: "available" if value is not None else "unavailable" for name, value in main_snapshot.items()},
            "main_unchanged": "pending" if all(value is not None for value in main_snapshot.values()) else "not_checked",
            "base_ancestry": "checked" if ancestry is not None else "not_checked",
        },
        "source_authority": {"path": SOURCE, "sha256": digest(ROOT / SOURCE), "fixture": FIXTURE, "fixture_sha256": digest(fixture_path)},
        "runtime": {},
        "cases": {},
        "browser_errors": [],
        "status": "RUNNING",
    }
    events = BrowserEvents()
    template = source_rows["semiconductor-rca"]
    models = {name: set_flow(template, labels, secondary=secondary, edge_label=edge_label)
              for name, (labels, secondary, edge_label) in cases.items()}
    try:
        with tempfile.TemporaryDirectory(prefix="visembler-chg293-native-") as temp_dir, sync_playwright() as playwright:
            with NativeHost(ROOT, Path(temp_dir) / "data") as host:
                report_ids = {name: host.create(model=model, name=f"chg293-{name}") for name, model in models.items()}
                browser = playwright.chromium.launch(**browser_kwargs())
                context = browser.new_context(viewport={"width": 390, "height": 900}, device_scale_factor=1, is_mobile=False)
                page = context.new_page()
                page.set_default_timeout(12000)
                events.attach(page)
                receipt["runtime"] = {"python": sys.version.split()[0], "nicegui": importlib.metadata.version("nicegui"), "playwright": importlib.metadata.version("playwright"), "browser": browser.version, "native_host": True, "ephemeral_port": host.port}
                (output / "screenshots").mkdir()
                for name, (labels, _secondary, _edge_label) in cases.items():
                    widths = WIDTHS if name == "r6-like" else ((1440, 390) if name == "four-stage-holdout" else (390,))
                    receipt["cases"][name] = {"labels": labels, "screenshots": {}, "geometry": {}}
                    for width in widths:
                        try:
                            facts = preview(page, host, report_ids[name], width)
                        except Exception as error:
                            log_path = getattr(host, "log_path", None)
                            if log_path and Path(log_path).is_file():
                                receipt["native_server_log_tail"] = Path(log_path).read_text(encoding="utf-8", errors="replace")[-30000:]
                            receipt["failed_capture"] = {"case": name, "width": width, "report_id": report_ids[name], "error": f"{type(error).__name__}: {error}"}
                            write_json(output / "acceptance.json", receipt)
                            raise
                        geometry = facts["geometry"]
                        assert "error" not in geometry, geometry
                        assert facts["model_snapshot"], "the saved report model must be available in Preview"
                        stem = f"{name}-{width}"
                        screenshot = output / "screenshots" / f"{stem}-full-page.png"
                        page.evaluate("window.scrollTo(0,0)")
                        page.screenshot(path=str(screenshot), full_page=True)
                        receipt["cases"][name]["geometry"][str(width)] = geometry
                        receipt["cases"][name]["screenshots"][str(width)] = {"path": screenshot.relative_to(output).as_posix(), "sha256": digest(screenshot), "width": width, "bytes": screenshot.stat().st_size}
                        if phase != "reproduction":
                            assert all(edge["text_intersections"] == 0 for edge in geometry["connectors"]), (name, width, geometry)
                            clearances = [value for edge in geometry["connectors"] for value in (edge["shaft_clearance_px"], edge["arrowhead_clearance_px"]) if value is not None]
                            assert clearances and min(clearances) >= 4, (name, width, geometry)
                            if geometry["edgeLabels"]:
                                assert geometry["edgeLabelToNodeTextClearancePx"] > 0, (name, width, geometry)
                        if name == "r6-like":
                            expected_projection = "wide" if width > 520 else "narrow" if width <= 360 else None
                            if expected_projection:
                                assert geometry["projection"] == expected_projection, (width, geometry)
                            else:
                                assert geometry["projection"].startswith("medium-"), (width, geometry)
                        if name in ("five-stage-holdout", "six-stage-holdout", "edge-secondary-labels"):
                            if phase != "reproduction":
                                assert geometry["readingColumns"] == 1, (name, geometry)
                        assert [node["order"] for node in geometry["nodes"]] == list(range(len(labels))), (name, width, geometry)
                        assert [node["title"].split(": ", 1)[-1].split(" · ", 1)[0] for node in geometry["nodes"]] == labels, (name, width, geometry)
                        assert [edge["order"] for edge in geometry["connectors"]] == list(range(len(labels) - 1)), (name, width, geometry)
                    # Reload from the native repository and compare the canonical graph identity.
                    reloaded = host.repository.get(report_ids[name]).model
                    assert flow_entry(reloaded)["diagram"] == models[name]["items"][[i for i,item in enumerate(models[name]["items"]) if item.get("element") == "Process Flow"][0]]["diagram"], name
                receipt["browser_errors"] = events.unexpected
                assert not events.unexpected, events.unexpected
                context.close()
                browser.close()
        if phase == "reproduction":
            r6_390 = receipt["cases"]["r6-like"]["geometry"]["390"]
            receipt["reproduced_collision_at_390"] = any(edge["text_intersections"] for edge in r6_390["connectors"])
            assert receipt["reproduced_collision_at_390"], r6_390
        main_after = {
            "local_main": optional_ref("refs/heads/main"),
            "origin_main": optional_ref("refs/remotes/origin/main"),
        }
        receipt["main_after"] = main_after
        receipt["lineage"]["main_refs_after"] = {
            name: "available" if value is not None else "unavailable" for name, value in main_after.items()
        }
        if all(value is not None for value in (*main_snapshot.values(), *main_after.values())):
            receipt["main_unchanged"] = main_after == main_snapshot
            receipt["lineage"]["main_unchanged"] = "checked"
        else:
            receipt["main_unchanged"] = None
            receipt["lineage"]["main_unchanged"] = "not_checked"
        if strict_lineage:
            assert receipt["main_unchanged"], {"before": main_snapshot, "after": main_after}
            assert receipt["base_is_ancestor"], {"base": BASE_SHA, "head": head}
        receipt["status"] = "PASS"
    except Exception as error:
        receipt["status"] = "FAIL"
        receipt["failure"] = f"{type(error).__name__}: {error}"
        if events.unexpected:
            receipt["browser_errors"] = events.unexpected
        write_json(output / "acceptance.json", receipt)
        raise
    write_json(output / "acceptance.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--phase", choices=("reproduction", "candidate", "local"), default="local")
    parser.add_argument("--candidate-sha", default="")
    parser.add_argument("--candidate-tree", default="")
    args = parser.parse_args()
    result = run_acceptance(args.output, phase=args.phase, candidate_sha=args.candidate_sha, candidate_tree=args.candidate_tree)
    print(json.dumps({"status": result["status"], "output": str(args.output.resolve()), "cases": list(result["cases"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
