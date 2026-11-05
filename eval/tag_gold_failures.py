"""Tag each gold-patch failure with a cause and whether the scorer would fail it too.

Input: gold results jsonl with row['diag'] (lines/err). Output: schema-headed jsonl.
scorer_fail: 'verified' = cause proven from the official wheelhouse/harness contents (package absent);
'assumed' = code-read of published harness says it fails, not run in the real scorer;
'unknown' = cause not established.
"""
import json, os, re, sys
src, out = sys.argv[1], sys.argv[2]
rows = [json.loads(l) for l in open(src)]
# Gold-PASSING tasks can also be excluded (dec 014):
#  null_pass: passes with a no-source-change patch (GOLD_NULL_RESULTS = null-control results jsonl).
#  wheel_shadowing: repo in SHADOWED_REPOS imports from the RECORD-stripped wheel copy in site-packages,
#  so workspace edits are not exercised (swegemma container_setup.py:266 strips RECORD -> editable install
#  cannot uninstall the wheel; src-layout package loses to site-packages).
NULL_SRC = os.environ.get('GOLD_NULL_RESULTS', '')
null_pass = {r['instance_id'] for r in map(json.loads, open(NULL_SRC)) if r.get('resolved')} if NULL_SRC else set()
SHADOWED = {x for x in os.environ.get('SHADOWED_REPOS', '').split(',') if x}
RICH_PYGMENTS = 'assert_diff_ansi_truecolor'  # syntax-highlight colour diffs: Pygments 2.21 vs period pins

def tag(r):
    d = r.get('diag') or {}
    txt = '\n'.join(d.get('lines', [])) + (d.get('err') or '')
    mods = sorted(set(re.findall(r"No module named '([^']+)'", txt)))
    if mods:
        return 'missing_module:' + ','.join(mods), 'verified', 'module has no wheel in official wheelhouse'
    if 'on_startup' in txt:
        return 'starlette_too_new', 'assumed', 'harness picks starlette 1.6.0 (max); Router on_startup removed'
    if 'httpbin' in txt:
        return 'httpbin_fixture_missing', 'verified', 'no pytest-httpbin/httpbin wheel in official wheelhouse'
    if r['repo'] == 'Textualize/rich' and '[38;2;' in txt and 'AssertionError' in txt:
        return 'pygments_version_output_diff', 'assumed', 'highlight colours differ under Pygments 2.21.0 (max)'
    if r['repo'] == 'Textualize/rich' and 'test_attrs_broken_310' in txt:
        return 'python_version_message_diff', 'assumed', 'test expects py3.10 AttributeError text; image is 3.13'
    if r.get('error') == 'Harness verification error':
        return 'harness_required_node_missing', 'assumed', 'pytest exit 0 but a required test node did not pass'
    return 'unexplained', 'unknown', 'not established; ' + (txt.strip().splitlines() or [''])[-1][:120]

with open(out, 'w') as fh:
    fh.write(json.dumps({'_schema': 'gold-failure-causes-v2', 'fields': 'instance_id,repo,exit_code,cause,scorer_fail,why,sample',
                         'source': src, 'null_source': NULL_SRC, 'shadowed_repos': sorted(SHADOWED),
                         'note': 'local faithful-emulation run (gold-local); scorer_fail in {verified,assumed,unknown,n/a}; '
                                 'every listed id is excluded from clean/dev/holdout'}) + '\n')
    for r in rows:
        if r['resolved']:
            if r['instance_id'] in null_pass:
                c, sf, why = 'null_pass', 'n/a', 'passes with null patch: test cannot discriminate a fix (dec 014)'
            elif r['repo'] in SHADOWED:
                c, sf, why = 'wheel_shadowing', 'n/a', 'package imports from site-packages wheel copy, not /workspace'
            else:
                continue
        else:
            c, sf, why = tag(r)
        fh.write(json.dumps({'instance_id': r['instance_id'], 'repo': r['repo'], 'exit_code': r['exit_code'], 'cause': c,
                             'scorer_fail': sf, 'why': why, 'sample': (r.get('diag') or {}).get('lines', [])[:2]}) + '\n')
