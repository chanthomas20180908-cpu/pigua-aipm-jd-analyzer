#!/usr/bin/env python3
"""目的：启动本地开发服务。

定义：`make dev` 调用的轻量开发服务器入口。

范围包括：
- 解析 host、port、reload 参数，加载仓库根目录 `.env`，启动 uvicorn。

范围不包括：
- 不写业务路由、分析逻辑或环境变量持久化逻辑。

使用与修改规则：
- 仅服务本地开发；生产启动方式应使用部署平台自己的进程管理。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the AI PM JD analyzer dev server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    parser.add_argument("--no-reload", action="store_true", help="Disable uvicorn reload.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(BASE_DIR / ".env")
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
    )


if __name__ == "__main__":
    main()
