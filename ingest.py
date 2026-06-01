#!/usr/bin/env python3
"""
Ingest -- feed anything into Vertical AI context
zip, dir, glob, cat, stdin
"""
import os, sys, zipfile, json, glob

MAX_CHARS = 6000

def ingest_zip(path):
    out = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if any(name.endswith(x) for x in ['.py','.js','.ts','.md','.txt','.json','.sh']):
                try:
                    out.append(f"### {name}\n{z.read(name).decode('utf-8','replace')[:800]}")
                except: pass
    return "\n\n".join(out)[:MAX_CHARS]

def ingest_dir(path):
    out = []
    for ext in ['*.py','*.js','*.ts','*.md','*.txt','*.sh']:
        for f in glob.glob(os.path.join(path,'**',ext), recursive=True):
            if '__pycache__' in f or '.git' in f: continue
            try:
                content = open(f,'r',errors='replace').read()[:800]
                out.append(f"### {f}\n{content}")
            except: pass
    return "\n\n".join(out)[:MAX_CHARS]

def ingest_files(patterns):
    out = []
    for pattern in patterns:
        for f in glob.glob(pattern, recursive=True):
            try:
                out.append(f"### {f}\n{open(f,'r',errors='replace').read()[:800]}")
            except: pass
    return "\n\n".join(out)[:MAX_CHARS]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--zip')
    g.add_argument('--dir')
    g.add_argument('--files', nargs='+')
    parser.add_argument('--out', default='ingest_output.txt')
    args = parser.parse_args()

    if args.zip:
        result = ingest_zip(args.zip)
        label = os.path.basename(args.zip)
    elif args.dir:
        result = ingest_dir(args.dir)
        label = os.path.basename(args.dir.rstrip('/'))
    else:
        result = ingest_files(args.files)
        label = "files"

    with open(args.out, 'w') as f:
        f.write(result)

    print(f"Ingested {len(result)} chars from {label}")
    print(f"Saved to {args.out}")
    print(f"\nRun boardroom:")
    print(f"  python vertical_ai.py --file {args.out}")
