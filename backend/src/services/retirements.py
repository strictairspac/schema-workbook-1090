import hashlib,json
from sqlalchemy import select
from fastapi import HTTPException
from src.models.entities import Relation,Dependency,Report,Retirement,Audit
from src.utils.serialization import record
from .common import save
from .normalization import closure,candidate_keys

def listing(db):return [record(x) for x in db.scalars(select(Retirement).order_by(Retirement.id.desc()))]

def _single_rhs_fds(deps):return [(frozenset(d.lhs),rhs) for d in deps for rhs in d.rhs]

def _baseline(relation,deps):
    payload={'attributes':sorted(relation.attributes),'dependencies':sorted((sorted(d.lhs),sorted(d.rhs)) for d in deps)}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def _impact(db,relation,deps,field):
    """沿依赖传递做污染分析：从退役字段出发，凡决定项被波及的规则，其被决定项也视为受影响。"""
    attrs=list(relation.attributes)
    if field not in attrs:raise HTTPException(422,'字段不存在或已下线，无需重复下线')
    tainted={field};growing=True
    while growing:
        growing=False
        for d in deps:
            if tainted&set(d.lhs) and not set(d.rhs)<=tainted:tainted|=set(d.rhs);growing=True
    removed=[d for d in deps if field in d.lhs or field in d.rhs]
    affected=[d for d in deps if tainted&set(d.lhs+d.rhs)]
    removed_ids={d.id for d in removed}
    kept_fds=[(frozenset(d.lhs),r) for d in deps if d.id not in removed_ids for r in d.rhs]
    remaining=[a for a in attrs if a!=field]
    keys_before,_=candidate_keys(attrs,_single_rhs_fds(deps))
    keys_after=[k for k in candidate_keys(remaining,kept_fds)[0]] if remaining else []
    preserved=[sorted(k) for k in keys_before if field not in k and set(remaining)<=closure(k,kept_fds)]
    inflight=list(db.scalars(select(Report).where(Report.relation_id==relation.id,Report.status.in_(('queued','running')))))
    blockers=[]
    if not remaining:blockers.append('不能下线关系的唯一属性，至少保留一个属性')
    if remaining and not preserved:blockers.append('下线后原候选键全部失效，请先调整依赖保住候选键')
    if inflight:blockers.append('存在在途报告（'+'、'.join('#%s %s'%(r.id,r.name) for r in inflight)+'），待完成后再确认')
    return {'field':field,'relation_code':relation.code,'affected_attributes':sorted(tainted),'remaining_attributes':remaining,
        'removed_dependencies':[{'id':d.id,'lhs':d.lhs,'rhs':d.rhs} for d in removed],
        'affected_dependencies':[{'id':d.id,'lhs':d.lhs,'rhs':d.rhs} for d in affected],
        'unfinished_reports':[{'id':r.id,'name':r.name,'status':r.status} for r in inflight],
        'candidate_keys_before':[sorted(k) for k in keys_before],'candidate_keys_after':[sorted(k) for k in keys_after],
        'preserved_keys':preserved,'key_preserved':bool(preserved),'blockers':blockers}

def _deps(db,relation_id):return list(db.scalars(select(Dependency).where(Dependency.relation_id==relation_id)))

def create(db,relation_id,data,user):
    relation=db.get(Relation,relation_id)
    if not relation:raise HTTPException(404,'关系不存在')
    deps=_deps(db,relation_id)
    existing=db.scalar(select(Retirement).where(Retirement.relation_id==relation_id,Retirement.field==data.field,Retirement.status.in_(('pending','conflict','failed'))).order_by(Retirement.id.desc()))
    if existing:  # 幂等：同字段已有未生效下线单，刷新预检后直接返回，不重复建单
        existing.impact=_impact(db,relation,deps,data.field);existing.baseline=_baseline(relation,deps);existing.status='pending'
        return save(db,existing,user,'刷新字段下线预检 '+relation.code+'/'+data.field)
    obj=Retirement(relation_id=relation_id,field=data.field,status='pending',baseline=_baseline(relation,deps),impact=_impact(db,relation,deps,data.field))
    return save(db,obj,user,'发起字段下线预检 '+relation.code+'/'+data.field)

def precheck(db,ident,user):
    obj=db.get(Retirement,ident)
    if not obj:raise HTTPException(404,'下线单不存在')
    if obj.status=='effective':raise HTTPException(409,'字段已下线生效，无需再次预检')
    relation=db.get(Relation,obj.relation_id)
    deps=_deps(db,obj.relation_id)
    obj.impact=_impact(db,relation,deps,obj.field);obj.baseline=_baseline(relation,deps);obj.status='pending'
    return save(db,obj,user,'字段下线预检 '+relation.code+'/'+obj.field)

def confirm(db,ident,user):
    obj=db.get(Retirement,ident)
    if not obj:raise HTTPException(404,'下线单不存在')
    if obj.status=='effective':return record(obj)  # 幂等：已生效的重试直接返回，不重复下线
    if obj.status=='conflict':raise HTTPException(409,'预检已失效，请重新预检后再确认')
    relation=db.scalar(select(Relation).where(Relation.id==obj.relation_id).with_for_update())
    if not relation:raise HTTPException(404,'关系不存在')
    deps=_deps(db,relation.id)
    if not obj.baseline or obj.baseline!=_baseline(relation,deps):
        obj.status='conflict';save(db,obj,user,'字段下线预检失效 '+relation.code+'/'+obj.field)
        raise HTTPException(409,'预检期间属性或依赖已被修改，基线变化使预检失效，请重新预检')
    impact=_impact(db,relation,deps,obj.field)
    if impact['unfinished_reports']:raise HTTPException(409,'存在在途报告，待其完成后再确认下线')
    if not impact['remaining_attributes']:raise HTTPException(422,'不能下线关系的唯一属性')
    if not impact['key_preserved']:raise HTTPException(422,'下线后原候选键全部失效，请先调整依赖保住候选键')
    removed_ids={d['id'] for d in impact['removed_dependencies']}
    try:
        relation.attributes=impact['remaining_attributes']
        for d in deps:
            if d.id in removed_ids:db.delete(d)
        obj.status='effective';obj.impact=impact
        db.add(obj);db.add(Audit(actor=user.email,action='字段下线生效 '+relation.code+'/'+obj.field));db.commit()
    except Exception:
        db.rollback()  # 失败回滚草案：属性与依赖保持原样
        try:
            fresh=db.get(Retirement,ident);fresh.status='failed'
            db.add(Audit(actor=user.email,action='字段下线失败已回滚 '+relation.code+'/'+obj.field));db.commit()
        except Exception:db.rollback()
        raise HTTPException(500,'下线应用失败，草案已回滚，请重试')
    return record(obj)
