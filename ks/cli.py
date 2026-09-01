"""CLI của KS. Mỗi lệnh tự mở/đóng connection và tự commit."""

from __future__ import annotations

import argparse
import sys

from ks import db
from ks.ingest import ingest_concepts
from ks.models import ConceptDraft, SourceModule


# ---------------------------------------------------------------- commands


def cmd_migrate(args) -> int:
    with db.connect() as conn:
        ran = db.migrate(conn)
    if ran:
        for name in ran:
            print(f"đã chạy: {name}")
    else:
        print("không có migration mới")
    return 0


def cmd_create_node(args) -> int:
    draft = ConceptDraft(
        title=args.title,
        subject=args.subject,
        summary=args.summary,
        source_module=SourceModule(args.source_module),
    )
    with db.connect() as conn:
        result = ingest_concepts(conn, [draft])
        conn.commit()
    item = result.ingested[0]
    verb = "tạo mới" if item.created else "gộp vào node có sẵn"
    print(f"{verb}: {item.node_id}")
    if item.candidates:
        print("candidate gần giống:")
        for cand in item.candidates:
            print(f"  {cand.score:.3f}  {cand.title}  ({cand.node_id})")
    return 0


# ---------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ks", description="Knowledge Store CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("migrate", help="Chạy migration chưa áp dụng")
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser("create-node", help="Tạo một khái niệm (qua dò trùng)")
    p.add_argument("--title", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument(
        "--source-module",
        default=SourceModule.MNEMOSYNE.value,
        choices=[m.value for m in SourceModule],
    )
    p.set_defaults(func=cmd_create_node)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
