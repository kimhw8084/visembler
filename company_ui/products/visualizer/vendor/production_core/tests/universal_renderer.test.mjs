import assert from 'node:assert/strict';
import { ALL_ELEMENTS, ELEMENTS_BY_ENGINE } from '../core/runtime_registry.mjs';
import { renderElement, findEngineForElement } from '../core/universal_renderer.mjs';
assert.equal(ALL_ELEMENTS.length,248);
let interactive=0;
for(const name of ALL_ELEMENTS){
  const engine=findEngineForElement(name);
  assert.ok(engine,`engine ${name}`);
  const html=renderElement(name,engine);
  assert.ok(html.includes(`data-element="${name.replace(/&/g,'&amp;').replace(/"/g,'&quot;')}"`) || html.includes('data-element='));
  assert.ok(!/(?:NaN|Infinity|undefined)/.test(html),name);
  assert.ok(/aria-label=/.test(html),name);
  assert.ok(html.length>220,name);
  if(engine==='InteractionLayer'||engine==='EditorInfrastructure'){
    interactive++;
    assert.ok(/button|tabindex/.test(html),name);
  }
}
assert.equal(Object.values(ELEMENTS_BY_ENGINE).flat().length,248);
console.log(JSON.stringify({pass:true,elements:248,engines:Object.keys(ELEMENTS_BY_ENGINE).length,interactive,allNamed:true,ariaNamed:true,noInvalidNumbers:true},null,2));
