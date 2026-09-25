from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / "tests" / "fixtures" / "chg208" / "chg173-remap-scenes.json"


def node_json(source: str) -> dict:
    env = os.environ.copy()
    env["CHG208_SCENES"] = SCENES.read_text(encoding="utf-8")
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", source],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise AssertionError(f"Node fixture failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def test_chg173_failure_paste_keeps_header_identity_and_observed_category_type() -> None:
    result = node_json(
        r'''
import {intakeText,datasetFromIntake} from './company_ui/products/visualizer/assets/authoring_data.mjs';
import {buildReusableBindingContract,suggestSlotMapping,planReusableRemap} from './company_ui/products/visualizer/assets/authoring_reuse_contract.mjs';
import {summarizedRemapIssues} from './company_ui/products/visualizer/assets/authoring_reuse_presentation.mjs';
const scene=JSON.parse(process.env.CHG208_SCENES),sample=scene.incompatible,dataset=datasetFromIntake(intakeText(sample.destination_paste_tsv),'target-data','Pasted data');
const contract=buildReusableBindingContract(sample.source.model),mapping=suggestSlotMapping(contract.slots[0],dataset),plan=planReusableRemap(contract,[dataset]),issues=summarizedRemapIssues(contract.slots[0],mapping);
const valueProblem=mapping.problems.find(problem=>problem.role==='value'&&problem.diagnostic_kind==='same_name_wrong_type');
console.log(JSON.stringify({evidenceCommit:scene.evidence.commit,header:dataset.metadata.header,names:dataset.fields.map(field=>field.name),types:dataset.fields.map(field=>field.type),rows:dataset.rows,sourceFields:contract.slots[0].source_fields.map(field=>[field.name,field.type]),ready:mapping.ready,planOk:plan.ok,valueProblem,issues:issues.map(issue=>issue.message),missing:mapping.unresolved.filter(issue=>issue.reason==='required field not found').map(issue=>issue.source_field)}));
'''
    )
    assert result["evidenceCommit"] == "7224c0815142557e2362e2ca4e6201e67006126c"
    assert result["header"]["present"] is True
    assert result["names"] == ["Cycle", "Failure count"]
    assert result["types"] == ["categorical", "categorical"]
    assert result["rows"] == [["C4", "none"], ["C5", "high"]]
    assert result["sourceFields"] == [["Cycle", "categorical"], ["Failure count", "integer"]]
    assert result["ready"] is False and result["planOk"] is False
    assert result["valueProblem"]["observed_field"] == {
        "id": "failure_count_2",
        "name": "Failure count",
        "type": "categorical",
        "semantic_tags": [],
        "dataset_name": "Pasted data",
    }
    assert result["valueProblem"]["expected_field"]["compatible_types"] == ["integer", "number"]
    assert any(
        "Failure count is Category in Pasted data" in issue
        and "Measurement requires a numeric field" in issue
        for issue in result["issues"]
    )
    assert "Failure count" not in result["missing"] and "Cycle" not in result["missing"]


def test_chg208_missing_ambiguous_and_unavailable_have_distinct_diagnostics() -> None:
    result = node_json(
        r'''
import {intakeText,datasetFromIntake} from './company_ui/products/visualizer/assets/authoring_data.mjs';
import {buildReusableBindingContract,suggestSlotMapping,planReusableRemap} from './company_ui/products/visualizer/assets/authoring_reuse_contract.mjs';
import {summarizedRemapIssues} from './company_ui/products/visualizer/assets/authoring_reuse_presentation.mjs';
const scene=JSON.parse(process.env.CHG208_SCENES),source=scene.ambiguous.source,contract=buildReusableBindingContract(source.model),target=datasetFromIntake(intakeText(scene.ambiguous.destination_paste_tsv),'ambiguous-data','Pasted data');
const auto=suggestSlotMapping(contract.slots[0],target),slotPlan=planReusableRemap(contract,[target]),categoryAmbiguity=auto.unresolved.find(issue=>issue.reason==='ambiguous'&&issue.role==='category'),ambiguousText=summarizedRemapIssues(contract.slots[0],auto).map(issue=>issue.message);
const chosen=planReusableRemap(contract,[target],{[contract.slots[0].identity]:{dataset_id:target.id,mappings:{c1:{category:'service_week_1'}}}});
const missingData={id:'missing-data',name:'Pasted data',fields:[{id:'shift',name:'Shift',type:'categorical'},{id:'note',name:'Note',type:'string'}],rows:[['C4','none'],['C5','high']]},missing=suggestSlotMapping(contract.slots[0],missingData),missingText=summarizedRemapIssues(contract.slots[0],missing).map(issue=>issue.message);
const unavailable=planReusableRemap(contract,[target],{[contract.slots[0].identity]:{dataset_id:target.id,mappings:{c1:{category:'deleted-service-week'}}}}),unavailableText=summarizedRemapIssues(contract.slots[0],unavailable.slots[0]).map(issue=>issue.message);
console.log(JSON.stringify({ambiguousNames:target.fields.map(field=>field.name),ambiguousCandidates:categoryAmbiguity?.candidate_fields?.map(field=>field.name),ambiguousText,ambiguousBlocked:!slotPlan.ok,chosenReady:chosen.ok,missingReasons:missing.unresolved.map(issue=>issue.reason),missingText,unavailableReason:unavailable.slots[0].problems[0]?.reason,unavailableKind:unavailable.slots[0].problems[0]?.diagnostic_kind,unavailableText,unavailableBlocked:!unavailable.ok}));
'''
    )
    assert result["ambiguousNames"] == ["Service week", "SERVICE WEEK", "SLA cases"]
    assert result["ambiguousCandidates"] == ["Service week", "SERVICE WEEK"]
    assert result["ambiguousBlocked"] is True and result["chosenReady"] is True
    assert any("Service week" in message and "SERVICE WEEK" in message for message in result["ambiguousText"])
    assert "required field not found" in result["missingReasons"]
    assert any("source field Service week is missing" in message for message in result["missingText"])
    assert result["unavailableReason"] == "selected field is unavailable"
    assert result["unavailableKind"] == "selected_field_unavailable"
    assert result["unavailableBlocked"] is True
    assert any("no longer available" in message and "Pasted data" in message for message in result["unavailableText"])
    assert not any("missing" in message.lower() for message in result["unavailableText"])


def test_chg208_shared_failure_summarizes_once_and_retains_field_identity() -> None:
    result = node_json(
        r'''
import {intakeText,datasetFromIntake} from './company_ui/products/visualizer/assets/authoring_data.mjs';
import {buildReusableBindingContract,suggestSlotMapping} from './company_ui/products/visualizer/assets/authoring_reuse_contract.mjs';
import {summarizedRemapIssues} from './company_ui/products/visualizer/assets/authoring_reuse_presentation.mjs';
const scene=JSON.parse(process.env.CHG208_SCENES),sample=scene.incompatible,model=structuredClone(sample.source.model),first=model.items[0],second={...structuredClone(first),id:'c2',element:'Pareto comparison',title:'Pareto comparison',order:1};model.items=[first,second];
const contract=buildReusableBindingContract(model),dataset=datasetFromIntake(intakeText(sample.destination_paste_tsv),'shared-target','Pasted data'),plan=suggestSlotMapping(contract.slots[0],dataset),issues=summarizedRemapIssues(contract.slots[0],plan),matching=issues.filter(issue=>issue.message.includes('Failure count is Category in Pasted data')&&issue.message.includes('Measurement requires a numeric field'));
console.log(JSON.stringify({slots:contract.slots.length,bindings:contract.slots[0].bindings.length,messages:matching.map(issue=>issue.message),itemIds:matching.map(issue=>issue.itemIds),elements:matching.map(issue=>issue.elements),count:matching.length}));
'''
    )
    assert result["slots"] == 1 and result["bindings"] == 2
    assert result["count"] == 1
    assert result["itemIds"] == [["c1", "c2"]]
    assert result["elements"] == [["Pareto", "Pareto comparison"]]
    assert "Affects 2 visuals." in result["messages"][0]


def test_chg208_browser_acceptance_is_registered_with_native_release_verifier() -> None:
    verifier = (ROOT / "scripts" / "verify_release.py").read_text()
    assert "run_chg208_remap_diagnostics_acceptance.py" in verifier
    assert "chg208-remap-diagnostics" in verifier
