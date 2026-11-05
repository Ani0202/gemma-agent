"""Build clean list + repo-stratified dev/holdout splits from gold results. Deterministic (sha256-keyed order)."""
import json,hashlib,sys,collections
src=sys.argv[1] if len(sys.argv)>1 else 'runs/gold-full/gold_results.jsonl'
rows=[json.loads(l) for l in open(src)]
clean=sorted(r['instance_id'] for r in rows if r['resolved'])
repo={r['instance_id']:r['repo'] for r in rows}
H=lambda ids:hashlib.sha256('\n'.join(ids).encode()).hexdigest()
by=collections.defaultdict(list)
for i in clean:by[repo[i]].append(i)
dev,hold=[],[]
for rp,ids in by.items():
    ids=sorted(ids,key=lambda i:hashlib.sha256(('gemma-split-v1'+i).encode()).hexdigest())
    k=round(len(ids)*0.3) if len(ids)>=3 else 0  # tiny repos stay in dev
    hold+=ids[:k];dev+=ids[k:]
dev.sort();hold.sort()
for n,ids in(('clean',clean),('dev',dev),('holdout',hold)):
    open(f'eval/splits/{n}.txt','w').write('\n'.join(ids)+'\n')
meta={'schema':'gold-calibration-splits-v2','n_total':len(rows),'n_clean':len(clean),'n_dev':len(dev),'n_holdout':len(hold),
 'sha256':{'clean':H(clean),'dev':H(dev),'holdout':H(hold)},
 'per_repo':{rp:{'total':sum(1 for r in rows if r['repo']==rp),'clean':len(by.get(rp,[])),'holdout':sum(1 for i in hold if repo[i]==rp)} for rp in sorted(set(repo.values()))},
 'source':src,'note':(sys.argv[2] if len(sys.argv)>2 else '')}
json.dump(meta,open('eval/splits/MANIFEST.json','w'),indent=1)
print(json.dumps(meta,indent=1))
