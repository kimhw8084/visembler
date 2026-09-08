"""Visible-image assertions shared by portability checks.

Checks actual CSS/IMG resources and decoding, not captions or asset-id presence.
Works on the live editor and the separately opened standalone SVG. It does not
change application state, synthesize media, or replace missing image resources.
"""
from __future__ import annotations
import json
from typing import Any


def assert_rendered_media(page: Any, item_id: str, *, width: int, height: int) -> dict[str, Any]:
    selector = f'#hull .component[data-id={json.dumps(item_id)}]'
    component = page.locator(selector)
    component.wait_for(state='visible', timeout=10000)
    # Image elements in this editor may use CSS backgrounds rather than <img>.
    sources = component.evaluate(r'''async component => {
      const found=[];
      for (const node of [component,...component.querySelectorAll('*')]) {
        const cs=getComputedStyle(node), r=node.getBoundingClientRect();
        if(cs.display==='none'||cs.visibility==='hidden'||r.width<=0||r.height<=0)continue;
        let source=node.tagName.toLowerCase()==='img'?(node.currentSrc||node.getAttribute('src')):'';
        const bg=cs.backgroundImage.match(/^url\((.*)\)$/);
        if(!source&&bg){source=bg[1];if((source.startsWith('"')&&source.endsWith('"'))||(source.startsWith("'")&&source.endsWith("'")))source=source.slice(1,-1);}
        if(!source)continue;
        let timer;
        const image=new Image();image.src=source;
        try {
          await Promise.race([image.decode(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Image decode timed out')),10000);})]);
        } finally { clearTimeout(timer); }
        found.push({source:source.startsWith('data:')?source.split(',')[0]:(new URL(source,document.baseURI)).pathname,
          embedded:source.startsWith('data:'),natural_width:image.naturalWidth,natural_height:image.naturalHeight,
          visible_width:r.width,visible_height:r.height});
      }
      return found;
    }''')
    assert sources, f'{item_id}: visible media has no image resource; a caption/placeholder is not a loaded image'
    assert any(s['natural_width']==width and s['natural_height']==height for s in sources), (
        f'{item_id}: expected decoded {width}x{height} image; observed {sources}')
    return {'item_id': item_id, 'status': 'PASS', 'resources': sources}
