# GH-WeeklyReport

本地/局域网周报分析工具：读取同模板 Excel 周报，整理当前周、跨周汇总、游戏详情收益汇总和趋势图。

## 环境要求

- Windows 10/11
- Node.js 18 或更高版本
- Python 3.9 或更高版本（需可通过 `python` 命令调用）
- 周报 `.xlsx` 文件目录

## 启动

1. 克隆仓库并进入项目目录。
2. 将周报 Excel 放到项目下的 `data` 文件夹，或启动后在页面顶部切换到实际周报目录。
3. 运行 `Start-WeeklyReportLan.ps1`，或执行 `npm start`。
4. 浏览器打开 `http://localhost:8787/`。

如需局域网其他设备访问，可用管理员权限运行 `启用局域网访问.ps1`，并确保客户端和主机位于同一局域网。

## 功能

- 当前周报：汇总、游戏明细、新游名单、周报文件切换与下载。
- 汇总：六个收益模块跨周去重累计、时间段筛选、异常波动标记。
- 游戏详情收益汇总下载：九游和腾讯合并为单表，同名游戏合并，包含 `序号/游戏名/注册汇总/付费汇总/收益汇总/平均收益`。
- 可视化：模块/指标/日期范围与对比区间选择、趋势点提示。
- 服务每日自动检查周报更新；配置与缓存保存在 `%APPDATA%\周报分析器`。

## 数据与隐私

周报数据可能包含业务敏感信息。本仓库不附带任何周报文件；不要将真实周报、缓存文件或个人配置提交到公开仓库。Excel 模板结构变化时，需要相应更新 `server/parser.py`。

## 常用接口

- `GET /api/health`：服务健康状态
- `GET /api/status`：当前目录、缓存状态、局域网地址
- `GET /api/files`：周报文件列表
- `GET /api/data`：当前最新周报数据
- `GET /api/aggregate`：跨周汇总
- `GET /api/aggregate/detail-export`：下载合并后的游戏详情收益汇总 CSV
- `POST /api/refresh`：重新扫描并解析
- `POST /api/config`：切换 Excel 目录

## 目录结构

```text
public/       页面、样式、图表交互
server/       Node.js 服务与 Python Excel 解析器
assets/       项目图标
```
