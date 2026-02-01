#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--template", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--server-name", required=True)
    p.add_argument("--ssl-cert", required=True)
    p.add_argument("--ssl-key", required=True)
    args = p.parse_args()

    tpl = Path(args.template).read_text(encoding="utf-8")
    rendered = (
        tpl.replace("__SERVER_NAME__", args.server_name)
        .replace("__SSL_CERT__", args.ssl_cert)
        .replace("__SSL_KEY__", args.ssl_key)
    )
    Path(args.out).write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

