<!--
目的：定义 v4 LLM-Native 子模块框架和所有可注册子模块。
定义：v4 主链路的原子分析单元目录，包含 SubModule 基类和子模块库。
范围包括：
- SubModule 运行协议。
- 内联 system prompt、输出 schema、user prompt 构造函数和子模块注册表。
范围不包括：
- 不承载 FastAPI 路由、前端渲染或旧版规则 parser。
- 不在子模块内写跨模块流程控制。
使用与修改规则：
- 子模块输出必须保持 JSON 可解析，并与前端字段标签配置保持兼容。
- 新增模块要同步 app/config/workflow_v4.py。
-->

# sub_modules 目录说明

## 目的
定义 v4 LLM-Native 子模块框架和所有可注册子模块。

## 定义
v4 主链路的原子分析单元目录，包含 SubModule 基类和子模块库。

## 范围包括
- SubModule 运行协议。
- 内联 system prompt、输出 schema、user prompt 构造函数和子模块注册表。

## 范围不包括
- 不承载 FastAPI 路由、前端渲染或旧版规则 parser。
- 不在子模块内写跨模块流程控制。

## 使用与修改规则
- 子模块输出必须保持 JSON 可解析，并与前端字段标签配置保持兼容。
- 新增模块要同步 app/config/workflow_v4.py。

