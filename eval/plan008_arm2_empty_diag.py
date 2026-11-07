import json,re,sys
ids=sys.argv[1].split(',')
W=re.compile(r"(sed -i|\bmv\b|\bcp\b|\btee\b|>\s*(?!/tmp|/dev)[\w./-]+\.py|git (checkout|restore|stash|reset)|python3? -c .*(open\(|write))")
for i in ids:
    t=json.load(open(f'runs/31b-v011-p8b-arm2/runs/{i}/trace.json'))
    E=t['entries']; calls=[];n=0
    for e in E:
        if e['type']=='tool_call':
            n+=1; calls.append([n,e['tool'],e.get('args') or {},None])
        elif e['type']=='tool_response' and calls:
            calls[-1][3]=e.get('result')
    ed=[(c[0],c[1],'ERR' if ('error' in str(c[3])[:200].lower()) else 'ok') for c in calls if c[1] in ('edit_file','write_file')]
    wr=[]
    for c in calls:
        if c[1]=='run_command':
            cmd=c[2].get('command','')
            shell=[l for l in cmd.split('\n') if not l.startswith((' ','\t'))][:3] if '<<' in cmd else [cmd]
            m=[s for s in shell if W.search(s)]
            if m: wr.append((c[0], m[0][:90]))
    diffs=[(c[0],str(c[3])[:120].replace('\\n',' ')) for c in calls if c[1]=='run_command' and 'git diff' in c[2].get('command','') ]
    last=calls[-1][1] if calls else None
    warn=next((c[0] for c in calls if 'budget_warning' in str(c[3])),None)
    print(f"== {i} calls={n} last={last} first_budget_warn={warn}")
    print('  edits:',ed)
    print('  ws-writes:',wr)
    print('  diffs:',diffs[-3:])
