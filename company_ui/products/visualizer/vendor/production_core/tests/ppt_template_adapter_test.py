#!/usr/bin/env python3
from pathlib import Path
import json,sys
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, MSO_SHAPE
from pptx.util import Inches,Pt
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from ppt_template_adapter import insert,rect,overlap
qa=ROOT/'qa';qa.mkdir(exist_ok=True)
template=qa/'ppt_template_fixture.pptx';out=qa/'ppt_middle_region_proof.pptx'
prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5);slide=prs.slides.add_slide(prs.slide_layouts[6])
# Existing corporate bands/logo: names and geometry must survive.
header=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(.3),Inches(.18),Inches(12.73),Inches(.72));header.name='CORP_HEADER';header.text='CORPORATE TEMPLATE'
logo=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(11.7),Inches(.24),Inches(1.0),Inches(.45));logo.name='CORP_LOGO';logo.text='LOGO'
footer=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(.3),Inches(7.02),Inches(12.73),Inches(.28));footer.name='CORP_FOOTER';footer.text='Confidential · 27'
prs.save(template)
prs=Presentation(template);before={s.name:rect(s) for s in prs.slides[0].shapes};target,added=insert(prs,0,placeholder='VISUALIZER_CONTENT');prs.save(out)
check=Presentation(out);after={s.name:rect(s) for s in check.slides[0].shapes if s.name in before}
original_unchanged=before==after
within=all(a['x']>=target['x']-1e-6 and a['y']>=target['y']-1e-6 and a['x']+a['width']<=target['x']+target['width']+1e-6 and a['y']+a['height']<=target['y']+target['height']+1e-6 for a in added)
obstacles=[before['CORP_HEADER'],before['CORP_LOGO'],before['CORP_FOOTER']];no_overlap=all(not overlap(a,o,0) for a in added for o in obstacles)
editable={'chart':any(getattr(s,'has_chart',False) for s in check.slides[0].shapes),'table':any(getattr(s,'has_table',False) for s in check.slides[0].shapes),'shapes':sum(1 for s in check.slides[0].shapes if s.name.startswith('VIZ::'))>=4}
report={'pass':original_unchanged and within and no_overlap and all(editable.values()),'originalShapesPreserved':original_unchanged,'target':target,'added':len(added),'withinTarget':within,'noCorporateOverlap':no_overlap,'editableObjects':editable,'output':str(out)}
(ROOT/'qa/ppt_template_adapter.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));sys.exit(0 if report['pass'] else 1)
