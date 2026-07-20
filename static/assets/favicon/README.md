# favicon 目录说明

## 目的

存放劈瓜站点在浏览器标签页和社交预览中复用的小尺寸品牌图标。

## 定义

`static/assets/favicon/` 是静态 favicon 资源目录。

## 范围包括

- 从现有品牌素材缩放或导出的 favicon 图片。
- 与浏览器图标显示直接相关的轻量资源。

## 范围不包括

- 不存放大图、页面插画、临时生成素材或第三方图库。
- 不承载 favicon 生成脚本。

## 使用与修改规则

- 更新图标后同步 HTML `<link rel="icon">` 和 `app/main.py` 的 `/favicon.ico` 路由。
