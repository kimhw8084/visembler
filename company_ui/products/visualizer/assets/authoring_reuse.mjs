export function reuseCapabilities({
  hasDataset=false,
  hasMapping=false,
  selectionCount=1,
  selectionLocked=false,
  clipboard=null,
}={}) {
  const payload=clipboard&&typeof clipboard==='object'?clipboard:null;
  const clipboardEntry=!!payload?.entry;
  const clipboardDataset=!!payload?.dataset;
  const clipboardComposition=payload?.kind==='composition'&&Array.isArray(payload.items)&&payload.items.length>1;

  return {
    copyVisual:selectionCount===1,
    copyStyle:selectionCount===1,
    copyData:selectionCount===1&&hasDataset,
    copyMapping:selectionCount===1&&hasDataset&&hasMapping,
    copySelection:selectionCount>1,
    cut:selectionCount>0&&!selectionLocked,
    pasteNew:!!payload&&(clipboardEntry||clipboardComposition),
    pasteStyle:selectionCount>0&&(!!payload?.style||clipboardEntry),
    pasteData:selectionCount===1&&hasDataset&&clipboardDataset,
    pasteMapping:selectionCount===1&&hasDataset&&clipboardEntry,
    appendData:selectionCount===1&&hasDataset&&clipboardDataset,
  };
}

export function reuseClipboardLabel(payload) {
  if(!payload)return 'Clipboard empty';
  if(payload.kind==='composition') {
    const count=Array.isArray(payload.items)?payload.items.length:0;
    return `${count} element${count===1?'':'s'} copied`;
  }
  const labels={
    visual_full:'Visual copied',
    dataset_data:'Data copied',
    mapping:'Mapping copied',
    style:'Style copied',
  };
  return labels[payload.kind]||'Reusable content copied';
}
