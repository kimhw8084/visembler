// Portable reports carry validated image bytes, never a server-local asset id.
// Canonical values and transform recipes are cloned, not rewritten/coerced.
export async function portableEnvelope(model, revision, resolveImage) {
  const clone=structuredClone(model), images=new Map();
  for (const entry of clone.items||[]) {
    if(entry.engine!=='ImageMediaEngine'||(!entry.src&&!entry.asset_id))continue;
    const original=entry.src||`/_cui_visualizer/report-assets/${entry.asset_id}`;
    let uri=images.get(original);
    if(!uri){uri=await resolveImage(original);images.set(original,uri);}
    if(!/^data:image\/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(uri))throw new Error('Image could not be embedded as validated PNG, JPEG, or WebP data.');
    entry.src=uri;delete entry.asset_id;
  }
  return {envelope:{schema_version:1,revision,model:clone},images};
}

export function inlineAssetUrls(style, images) {
  return String(style).replace(/url\(\s*(['"]?)(.*?)\1\s*\)/g,(whole,quote,url)=>images.has(url)?`url("${images.get(url)}")`:whole);
}
