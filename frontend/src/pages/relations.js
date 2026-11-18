import {table} from '../components/common/table.js';import {badge} from '../components/common/badge.js';import {esc,date} from '../utils/html.js';import {session} from '../hooks/session.js';
const depText=d=>`{ ${esc(d.lhs.join(', '))||'∅'} } → { ${esc(d.rhs.join(', '))} }`;
function impactCell(im){
  if(!im)return '<small>尚未生成预检，点「重新预检」计算影响范围。</small>';
  const removed=new Set(im.removed_dependencies.map(d=>d.id));
  const rules=im.affected_dependencies.length?im.affected_dependencies.map(d=>`<small>${removed.has(d.id)?'✕':'·'} ${depText(d)}${removed.has(d.id)?'（将删除）':'（波及）'}</small>`).join(''):'<small>无受影响规则</small>';
  const reports=im.unfinished_reports.map(r=>`<small>在途报告 #${r.id} ${esc(r.name)}</small>`).join('');
  const keys=im.key_preserved?`<small>候选键保住 ${esc(im.preserved_keys.map(k=>'{'+k.join(', ')+'}').join(' / '))}</small>`:'<small class="error">候选键无法保住</small>';
  return rules+reports+keys+(im.blockers||[]).map(b=>`<small class="error">⚠ ${esc(b)}</small>`).join('');
}
export function relationsPage(items,retirements){
  const canWrite=session.user.role!=='viewer';
  const rows=retirements.map(t=>{
    const code=items.find(r=>r.id===t.relation_id)?.code||'#';
    const actions=[];
    if(t.status==='pending')actions.push(`<button class="small confirm-retirement" data-id="${t.id}" ${!canWrite||(t.impact?.blockers||[]).length?'disabled':''}>确认生效</button>`);
    if(t.status!=='effective')actions.push(`<button class="small precheck-retirement" data-id="${t.id}" ${!canWrite?'disabled':''}>重新预检</button>`);
    return [`<strong>${esc(code)}</strong><span class="attribute">${esc(t.field)}</span><small>${date(t.created_at)}</small>`,badge(t.status),impactCell(t.impact),actions.join(' ')||'—'];
  });
  return `<div class="split"><section><div class="section-top"><h2>关系草案目录</h2><span>${items.length} 件 / ARCHIVE</span></div>${table(['档案编号 / 业务对象','属性集合','说明'],items.map(r=>[`<strong>${esc(r.code)}</strong><small>${esc(r.title)}</small>`,r.attributes.map(a=>`<span class="attribute">${esc(a)}</span>`).join(' '),esc(r.note)]))}<div class="notice">属性只是业务名称，不会执行为SQL。最多10个属性，精确搜索至多1024个子集；超限会给出明确错误。</div><div class="section-top"><h2>字段下线预检</h2><span>RETIREMENT / PRE-CHECK</span></div>${table(['草案 / 下线字段','状态','影响范围','操作'],rows)}<div class="notice">预检沿依赖传递找出受影响规则与在途报告，本身不改动数据。确认时若基线被并发编辑、候选键无法保住或存在在途报告，将拒绝生效；失败自动回滚草案，重试不会重复下线。已生效后已完成报告保留原快照，新报告不再引用该字段。</div></section><section class="form-panel"><span class="eyebrow">NEW RELATION DRAFT</span><h2>登记关系草案</h2><form id="relation-form"><label>草案编号<input name="code" placeholder="NL-1117-D" required></label><label>业务对象名称<input name="title" placeholder="检测委托明细" required></label><label>属性列表（逗号分隔）<input name="attributes" value="委托号,客户,检测项,方法,结果" required></label><label>业务备注<input name="note" value="先明确业务依赖，再讨论拆表"></label><button class="primary" ${canWrite?'':'disabled'}>保存关系草案 +</button></form><div class="form-divider"></div><span class="eyebrow">RETIRE A FIELD</span><h2>发起字段下线</h2><form id="retirement-form"><label>关系草案<select name="relation_id">${items.map(r=>`<option value="${r.id}">${esc(r.code)} · ${esc(r.title)}</option>`).join('')}</select></label><label>下线字段名<input name="field" placeholder="结果" required></label><button class="primary" ${canWrite?'':'disabled'}>预检影响范围 ↗</button></form><p class="help">属性必须非空、唯一，1–10项。无函数依赖时，完整属性集为候选键。下线字段名须与草案属性完全一致；预检生成影响范围后，需人工确认才会生效。</p></section></div>`;
}
