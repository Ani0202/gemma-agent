#!/usr/bin/env python3
"""Plan 009 rev 2 IDENTITY checks ZIP + CONTENT (eval/plans/009.md, IDENTITY block).

ZIP:     sha256(dist/31b-<v>.zip) == the 'zip sha256:' line of bundles/31b/<v>/MANIFEST.md.
CONTENT: zip member paths + per-file sha256 == files under bundles/31b/<v>/, excluding ONLY the
         root MANIFEST.md of the source dir (bin/pack strips it from the zip by design).
Also records sha256 of agent.yaml inside the zip (header agent_yaml_sha256 must equal it).
TRANSPORT is a separate check made at push time (journaled); it is not computed here.

Usage: eval/plan009_identity.py v012 [v013 ...] [--out results/plan009_bundle_identity.json] [--event smoke|main|chunkN]
Exit 0 iff every requested bundle passes ZIP and CONTENT. Appends one record per call to the output file.
"""
import argparse, datetime, hashlib, json, os, re, subprocess, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = ("plan009_bundle_identity v2 (records made before v2 lack duplicate_members): records[] each {utc, git_sha, event, bundles{<v>: {zip_path, zip_sha256, "
          "manifest_zip_sha256, zip_ok, content_ok, only_in_zip[], only_in_dir[], byte_mismatch[], duplicate_members[], excluded[], "
          "agent_yaml_sha256, pass}}}")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def check(v):
    bdir = os.path.join(ROOT, "bundles", "31b", v)
    zpath = os.path.join(ROOT, "dist", f"31b-{v}.zip")
    man = open(os.path.join(bdir, "MANIFEST.md")).read()
    m = re.search(r"zip sha256:\s*([0-9a-f]{64})", man)
    manifest_sha = m.group(1) if m else None
    with open(zpath, "rb") as f:
        zsha = sha(f.read())
    zfiles = {}
    dup = []
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            if info.filename in zfiles:
                dup.append(info.filename)  # duplicate member names could hide unmatched bytes
            zfiles[info.filename] = sha(z.read(info))
    dup = sorted(set(dup))
    dfiles = {}
    for dp, dn, fn in os.walk(bdir):
        for n in fn:
            full = os.path.join(dp, n)
            rel = os.path.relpath(full, bdir).replace(os.sep, "/")
            with open(full, "rb") as f:
                dfiles[rel] = sha(f.read())
    excluded = []
    if "MANIFEST.md" in dfiles:
        del dfiles["MANIFEST.md"]
        excluded.append("MANIFEST.md")
    only_z = sorted(set(zfiles) - set(dfiles))
    only_d = sorted(set(dfiles) - set(zfiles))
    mism = sorted(p for p in set(zfiles) & set(dfiles) if zfiles[p] != dfiles[p])
    zip_ok = manifest_sha is not None and manifest_sha == zsha
    content_ok = not (only_z or only_d or mism or dup)
    return {"zip_path": os.path.relpath(zpath, ROOT), "zip_sha256": zsha, "manifest_zip_sha256": manifest_sha,
            "zip_ok": zip_ok, "content_ok": content_ok, "only_in_zip": only_z, "only_in_dir": only_d,
            "byte_mismatch": mism, "duplicate_members": dup, "excluded": excluded, "agent_yaml_sha256": zfiles.get("agent.yaml"),
            "pass": zip_ok and content_ok and "agent.yaml" in zfiles}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("versions", nargs="+")
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "plan009_bundle_identity.json"))
    ap.add_argument("--event", default="check")
    a = ap.parse_args()
    git = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    rec = {"utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "git_sha": git,
           "event": a.event, "bundles": {v: check(v) for v in a.versions}}
    data = {"_schema": SCHEMA, "records": []}
    if os.path.exists(a.out):
        old = json.load(open(a.out))
        if not isinstance(old, dict) or not isinstance(old.get("records"), list):
            sys.exit(f"ERROR: {a.out} is not a records file; refusing to overwrite")
        data["records"] = old["records"]  # _schema is always rewritten to the current SCHEMA
    data["records"].append(rec)
    with open(a.out, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    ok = all(b["pass"] for b in rec["bundles"].values())
    for v, b in rec["bundles"].items():
        print(f"{v}: zip_ok={b['zip_ok']} content_ok={b['content_ok']} agent_yaml={b['agent_yaml_sha256']} pass={b['pass']}")
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
