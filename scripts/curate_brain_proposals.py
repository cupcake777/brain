#!/usr/bin/env python3
"""Prepare, check and atomically apply a digest-bound independent review plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hermes.proposal_curation import ProposalCuration
from hermes.repository import HermesRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--reviewer', required=True)
    prepare.add_argument('--session-id', required=True)
    prepare.add_argument('--output', required=True)
    for name in ('check', 'apply'):
        command = sub.add_parser(name)
        command.add_argument('--plan', required=True)
    args = parser.parse_args()
    curator = ProposalCuration(HermesRepository(args.db))
    if args.command == 'prepare':
        plan = curator.prepare(reviewer=args.reviewer, session_id=args.session_id)
        Path(args.output).write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'plan': args.output, 'pending': len(plan['decisions'])}))
    else:
        result = curator.apply(json.loads(Path(args.plan).read_text()), dry_run=args.command == 'check')
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
