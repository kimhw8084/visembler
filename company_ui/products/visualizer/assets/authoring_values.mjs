// Canonical scalar/grid editing semantics shared by Visembler authoring surfaces.
// Empty unquoted cell => null; quoted empty => intentional blank string.
// Unquoted plain numeric => number; quoted numeric => string.
const NUMERIC=/^[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?$/i;
const ID_LIKE=/^0\d+$/;

function delimiterFor(source){
  const first=String(source??'').split('\n').find(line=>line.trim())||'';
  const choices=[
    ['\t',(first.match(/\t/g)||[]).length],
    [',',(first.match(/,/g)||[]).length],
    [';',(first.match(/;/g)||[]).length],
  ].sort((a,b)=>b[1]-a[1]);
  return choices[0][1]?choices[0][0]:'\t';
}

function quotedLiteral(text){
  if(text.length<2||text[0]!=='"'||text.at(-1)!=='"')return null;
  return text.slice(1,-1).replace(/""/g,'"');
}

export function parseAuthoringScalar(raw,{quoted=false,type='unknown'}={}){
  const source=String(raw??'');
  if(quoted)return source;
  const text=source.trim();
  if(text==='')return null;

  // Direct single-cell editing can express string intent with quotes too.
  const explicit=quotedLiteral(text);
  if(explicit!==null)return explicit;

  if(type==='boolean'&&/^(true|false)$/i.test(text))return /^true$/i.test(text);

  const percentage=/^[-+]?(?:\d+\.?\d*|\.\d+)%$/.test(text);
  const currency=/^[\$€£¥]\s*[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?$/i.test(text);
  const normalized=text.replace(/[,$€£¥%\s]/g,'');
  const profiledNumeric=['integer','number'].includes(type);
  const directPlainNumeric=type==='unknown'&&!percentage&&!currency;

  if((profiledNumeric||directPlainNumeric)&&!ID_LIKE.test(text)&&NUMERIC.test(normalized)){
    const value=Number(normalized);
    if(Number.isFinite(value))return percentage?value/100:value;
  }
  return text;
}

export function formatAuthoringScalar(value){
  if(value===null||value===undefined)return '';
  if(typeof value==='number')return Number.isFinite(value)?String(value):String(value);
  if(typeof value==='boolean')return value?'true':'false';

  const text=String(value);
  if(text==='')return '""';

  // Quote strings that would otherwise be reparsed as a different scalar type,
  // or that need CSV/TSV escaping.
  const parsed=parseAuthoringScalar(text);
  const needsTypeQuote=typeof parsed!=='string'||parsed!==text;
  const needsDelimitedQuote=/[\t,;\n\r"]/.test(text)||text!==text.trim();
  if(!needsTypeQuote&&!needsDelimitedQuote)return text;
  return `"${text.replace(/"/g,'""')}"`;
}

export function parseDelimitedText(text,{limit=100001}={}){
  const source=String(text??'').replace(/^\uFEFF/,'').replace(/\r\n?/g,'\n');
  if(!source.trim())return {rows:[],quoted_rows:[],delimiter:null,warnings:[]};

  const delimiter=delimiterFor(source);
  const rows=[],quotedRows=[];
  let row=[],quotedRow=[],cell='',inQuotes=false,cellQuoted=false;

  const pushCell=()=>{
    row.push(cell);
    quotedRow.push(cellQuoted);
    cell='';
    cellQuoted=false;
  };
  const pushRow=()=>{
    rows.push(row);
    quotedRows.push(quotedRow);
    row=[];
    quotedRow=[];
  };

  for(let i=0;i<source.length;i+=1){
    const ch=source[i];
    if(ch==='"'){
      if(inQuotes&&source[i+1]==='"'){
        cell+='"';
        i+=1;
        continue;
      }
      if(!inQuotes&&cell===''){
        inQuotes=true;
        cellQuoted=true;
        continue;
      }
      if(inQuotes){
        inQuotes=false;
        continue;
      }
      cell+=ch;
      continue;
    }
    if(ch===delimiter&&!inQuotes){
      pushCell();
      continue;
    }
    if(ch==='\n'&&!inQuotes){
      pushCell();
      pushRow();
      if(rows.length>=limit){
        return {
          rows,
          quoted_rows:quotedRows,
          delimiter,
          warnings:[{code:'row_limit',message:`Only the first ${limit.toLocaleString()} rows were profiled.`}],
        };
      }
      continue;
    }
    cell+=ch;
  }

  pushCell();
  pushRow();

  if(source.endsWith('\n')&&rows.at(-1)?.every(value=>value==='')&&quotedRows.at(-1)?.every(value=>!value)){
    rows.pop();
    quotedRows.pop();
  }

  return {
    rows,
    quoted_rows:quotedRows,
    delimiter,
    warnings:inQuotes
      ? [{code:'unclosed_quote',message:'Input ended inside a quoted value; the final value was retained.'}]
      : [],
  };
}

export function parseAuthoringGrid(text){
  const parsed=parseDelimitedText(text);
  return {
    ...parsed,
    rows:parsed.rows.map((row,rowIndex)=>
      row.map((value,columnIndex)=>
        parseAuthoringScalar(value,{quoted:Boolean(parsed.quoted_rows[rowIndex]?.[columnIndex])})
      )
    ),
  };
}

export function formatAuthoringRow(row,delimiter='\t'){
  return (row||[]).map(formatAuthoringScalar).join(delimiter);
}
