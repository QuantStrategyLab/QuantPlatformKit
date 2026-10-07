"""Caller-owned engineering audit over a frozen, explicit material file."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from .task_review import review_material


def audit_material(material, *, roles, reviewer=review_material):
    if not isinstance(material, dict) or not {'repository','revision','objective','evidence'} <= set(material):
        raise ValueError('frozen caller material required')
    if not isinstance(material['repository'],str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',material['repository']):
        raise ValueError('caller repository required')
    if not isinstance(material['revision'],str) or not re.fullmatch(r'[0-9a-f]{40}',material['revision']):
        raise ValueError('frozen revision required')
    if not isinstance(material['objective'],str) or not material['objective'].strip():
        raise ValueError('caller objective required')
    encoded=json.dumps(material,sort_keys=True,ensure_ascii=False,allow_nan=False)
    if len(encoded.encode()) > 200000:
        raise ValueError('audit material too large')
    result=reviewer(material,operation_id='engineering-audit:'+hashlib.sha256(encoded.encode()).hexdigest(),required_roles=roles)
    return {'schema':'qsl.engineering_audit.v2','repository':material['repository'],'revision':material['revision'],
            'review':result,'advisory_only':True,'merge_authority_granted':False,'deployment_authority_granted':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--material',type=Path,required=True)
    parser.add_argument('--roles-json',required=True)
    args=parser.parse_args(argv)
    try:
        if args.material.is_symlink() or not args.material.is_file() or args.material.stat().st_size > 200000:
            raise ValueError('bounded material file required')
        roles=json.loads(args.roles_json)
        if not isinstance(roles,list) or not roles or any(not isinstance(r,str) or not r for r in roles) or len(set(roles))!=len(roles):
            raise ValueError('explicit unique roles required')
        result=audit_material(json.loads(args.material.read_text()),roles=roles)
    except Exception:
        print(json.dumps({'schema':'qsl.engineering_audit.v2','status':'unavailable','advisory_only':True}))
        return 3
    print(json.dumps(result,sort_keys=True))
    return 0 if result['review'].get('status')=='completed' else 3


if __name__=='__main__':
    raise SystemExit(main())
