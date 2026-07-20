<!--
目的：承载 FastAPI 后端、LLM 调用、v4 工作流、离线迭代 Loop 和保留兼容的旧版分析逻辑。
定义：后端应用包，是服务入口、业务编排、子模块定义、离线实验组件和旧版能力模块的代码边界。
范围包括：
- FastAPI 路由与请求模型。
- 静态页面路由、favicon 路由和品牌错误页 handler。
- LLM 客户端、trace logger、v4 workflow、SubModule 库、离线 iteration 组件和旧版 v2/v3 兼容代码。
范围不包括：
- 不放前端静态资源、测试集原始数据或运行日志。
- 不在旧版 v2/v3 文件中继续扩展新主链路能力。
使用与修改规则：
- 新功能优先围绕 /analyze/v4、app/workflows/analyze_jd_v4.py 和 app/sub_modules/ 扩展。
- 改动返回结构时同步检查 static/field-labels.js 和前端渲染。
-->

# app 目录说明

## 目的
承载 FastAPI 后端、LLM 调用、v4 工作流、离线迭代 Loop 和保留兼容的旧版分析逻辑。

## 定义
后端应用包，是服务入口、业务编排、子模块定义、离线实验组件和旧版能力模块的代码边界。

## 范围包括
- FastAPI 路由与请求模型。
- 静态页面路由、favicon 路由和品牌错误页 handler。
- LLM 客户端、trace logger、v4 workflow、SubModule 库、离线 iteration 组件和旧版 v2/v3 兼容代码。

## 范围不包括
- 不放前端静态资源、测试集原始数据或运行日志。
- 不在旧版 v2/v3 文件中继续扩展新主链路能力。

## 使用与修改规则
- 新功能优先围绕 /analyze/v4、app/workflows/analyze_jd_v4.py 和 app/sub_modules/ 扩展。
- 改动返回结构时同步检查 static/field-labels.js 和前端渲染。
