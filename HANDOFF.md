# GH-WeeklyReport 交接文档

## 项目定位

Windows 本地/局域网周报分析网站。后端为 Node.js 原生 HTTP 服务，Python 解析 `.xlsx` 文件；前端为静态 HTML/CSS/JavaScript。

## 运行与配置

- 启动：`npm start` 或执行 `Start-WeeklyReportLan.ps1`。
- 默认读取目录：项目根目录下的 `data`，网页顶部可切换目录。
- 端口：`8787`，可通过环境变量 `PORT` 覆盖。
- 持久化配置和缓存位于 `%APPDATA%\周报分析器`，不应纳入版本控制。
- Python 解析器调用：`python server/parser.py <data|aggregate|detail-aggregate> --dir <目录>`。

## 主要接口

- `GET /api/health`、`GET /api/status`、`GET /api/files`
- `GET /api/data`（可传 `?file=文件名` 读取指定周报）
- `GET /api/aggregate`
- `GET /api/aggregate/detail-export`：导出单表游戏收益汇总 CSV
- `POST /api/refresh`、`POST /api/config`

## 游戏详情收益汇总规则

- 从周报读取九游和腾讯游戏明细，按修改时间由新到旧处理。
- 同一周次优先使用较新的文件；九游与腾讯行按游戏名合并。
- 注册、付费、收益累计后按收益倒序排列。
- 表头：`序号、游戏名、注册汇总、付费汇总、收益汇总、平均收益`。
- 当前平均收益为收益汇总除以 7 天；如业务定义需要按累计周数平均，应修改 `server/parser.py` 中的计算规则。

## 代码入口

- `server/server.mjs`：HTTP 路由、缓存、目录配置、定时刷新和下载。
- `server/parser.py`：工作表读取、字段映射和汇总计算。
- `public/app.js`：页面渲染、筛选、交互和下载按钮。
- `public/styles.css`、`public/polish.css`：样式。

## 发布与维护注意事项

1. 确认真实周报、缓存、配置不在 Git 提交列表；仓库 `.gitignore` 已排除 `data/`、Excel、CSV 和 Python 缓存。
2. 运行 `node --check server/server.mjs`、`node --check public/app.js`、`python -m py_compile server/parser.py`。
3. 使用脱敏的同模板文件验证导出，不要将真实业务周报提交到公开仓库。
4. 解析器依赖既有工作表与列位置，模板变化时需更新 `server/parser.py`。
5. `启用局域网访问.ps1` 会新增 Windows 防火墙入站规则，仅在确有需要时以管理员运行。
6. `WeeklyReportLauncher.cs` 是启动器源代码；运行时从自身所在目录定位脚本，当前仓库未提供编译后的 EXE。
