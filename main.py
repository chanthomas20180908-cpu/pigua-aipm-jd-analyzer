"""目的：本地启动提示入口。

定义：根目录下的轻量说明脚本，提醒开发者使用 uvicorn 启动 app.main。

范围包括：
- 本地启动提示和项目入口说明。

范围不包括：
- 不承载 FastAPI 路由或业务逻辑。

使用与修改规则：
- 业务入口变更时同步本文件提示和 README 运行命令。
"""

def main() -> None:
    print("Run: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
