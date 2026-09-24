import { humanFieldTypeLabel, humanRoleLabel } from './authoring_human.mjs';

const text = value => String(value ?? '').trim();
const roleFamily = role => ({ x:'category', label:'category', y:'measurement', value:'measurement', timestamp:'time', datetime:'time', reference_value:'reference_value', affected_value:'affected_value' }[role] || role);
const roleName = (role, view = '') => {
  if (String(role || '').startsWith('$reference:')) return 'Recipe field';
  const family = roleFamily(role), fixed = { category:'Category', measurement:'Measurement', time:'Time', reference_value:'Reference', affected_value:'Affected', tool:'Tool', chamber:'Chamber', lot:'Lot', wafer:'Wafer', product:'Product', route:'Route', bin:'Bin' }[family];
  return fixed || humanRoleLabel(role,{view}) || 'Field';
};

function bindingRoles(binding = {}) {
  const known = new Set((binding.field_roles || []).map(value => value.role));
  return [
    ...(binding.field_roles || []),
    ...(binding.references || []).map(value => ({ ...value, role: value.role, label: 'Recipe field' })),
    ...(binding.required_roles || []).filter(role => !known.has(role)).map(role => ({ role, field_name: '', field_type: '', semantic_tags: [], required: true })),
  ];
}

export function remapVisualLabels(bindings = []) {
  const rows = (bindings || []).map(binding => ({ id:String(binding.item_id||''), name:text(binding.element||binding.item_id||'Visual') }));
  const counts = new Map();
  for (const row of rows) counts.set(row.name,(counts.get(row.name)||0)+1);
  return rows.map((row,index)=>counts.get(row.name)>1?`${row.name} ${rows.filter((other,otherIndex)=>other.name===row.name&&otherIndex<=index).length}`:row.name);
}

export function groupedRemapRequirements(source = {}, slot = {}, selection = {}) {
  const groups = new Map();
  for (const binding of source.bindings || []) for (const requirement of bindingRoles(binding)) {
    const family = roleFamily(requirement.role), label = requirement.label || roleName(requirement.role,binding.view);
    const key = JSON.stringify([family, label, requirement.field_name, requirement.field_type, requirement.semantic_tags || [], requirement.required === true]);
    if (!groups.has(key)) groups.set(key, { role: family, label, sourceField: text(requirement.field_name), sourceType: text(requirement.field_type), required: requirement.required === true, bindings: [] });
    let target = groups.get(key).bindings.find(value=>value.itemId===String(binding.item_id));
    if(!target){target={itemId:String(binding.item_id),element:text(binding.element||binding.item_id),view:binding.view||'',roles:[]};groups.get(key).bindings.push(target);}
    if(!target.roles.includes(requirement.role))target.roles.push(requirement.role);
  }
  return [...groups.values()].map(group => {
    const values = group.bindings.flatMap(binding=>binding.roles.map(role=>String(selection.mappings?.[binding.itemId]?.[role] || slot.mapping?.[binding.itemId]?.[role] || '')));
    const commonValue = values.length && values.every(value => value === values[0]) ? values[0] : '';
    const consumers = remapVisualLabels(group.bindings);
    return { ...group, itemIds: group.bindings.map(binding => binding.itemId), assignments:group.bindings.map(binding=>({itemId:binding.itemId,roles:binding.roles})), consumers, value: commonValue,
      consumersLabel: consumers.join(' · '), shared: group.bindings.length > 1,
      expectedTypeLabel: group.sourceType ? humanFieldTypeLabel(group.sourceType) : '' };
  });
}

function issueLabel(issue, source) {
  const binding = (source.bindings || []).find(value => String(value.item_id) === String(issue.item_id));
  return issue.label || roleName(issue.role, binding?.view);
}

function issueText(issue, label) {
  const sourceField = text(issue.source_field);
  if (issue.message) return text(issue.message).replace(/\s+/g, ' ');
  if (issue.reason === 'ambiguous') return `${sourceField || label} matches more than one field. Choose the intended ${label.toLowerCase()} field.`;
  if (issue.reason === 'incompatible type' || issue.reason === 'field type is incompatible') {
    const requiredType = issue.role === 'time' ? 'a date or time field' : ['value','y','size','weight','reference_value','affected_value'].includes(issue.role) ? 'a numeric field' : 'a compatible field';
    return `${sourceField || label} needs ${requiredType} for ${label.toLowerCase()}.`;
  }
  if (issue.reason === 'required field not found') return `Required source field ${sourceField || label} is missing.`;
  if (issue.reason === 'required role is unmapped' || issue.reason === 'Choose a compatible field') return `Choose a compatible field for ${label.toLowerCase()}.`;
  if (issue.reason === 'selected field is unavailable') return `The selected ${label.toLowerCase()} field is unavailable. Choose another field.`;
  return sourceField ? `${sourceField}: ${text(issue.reason) || 'Review this field mapping.'}` : `${label}: ${text(issue.reason) || 'Review this field mapping.'}`;
}

export function summarizedRemapIssues(source = {}, slot = {}) {
  const groups = new Map();
  for (const [kind, issues] of [['unresolved', slot.unresolved || []], ['problem', slot.problems || []]]) for (const issue of issues) {
    const label = issueLabel(issue, source), message = issueText(issue, label), key = `${label}|${message}`;
    if (!groups.has(key)) groups.set(key, { label, message, itemIds: new Set(), elements: new Set(), kind });
    const group = groups.get(key), binding = (source.bindings || []).find(value => String(value.item_id) === String(issue.item_id));
    if (issue.item_id) group.itemIds.add(String(issue.item_id));
    if (binding) group.elements.add(text(binding.element || binding.item_id));
  }
  return [...groups.values()].map(group => ({ ...group, itemIds: [...group.itemIds], elements: [...group.elements],
    message: group.elements.size > 1 ? `${group.message} · Affects ${group.elements.size} visuals.` : group.message }));
}

export function remapStatusSummary(plan = {}) {
  if (plan.ok) return 'All data requirements are compatible.';
  return 'Resolve the highlighted data source and field requirements before applying.';
}
