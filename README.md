# Insight 经营分析系统

产品中心经营分析平台 — 管理5个事业部的年度目标、月度完成情况与商机。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + Vite + Element Plus + ECharts |
| 后端 | Python 3.11 + FastAPI + SQLModel |
| 数据库 | SQLite（单文件，自动初始化） |
| 容器 | Docker + docker-compose |

## 快速启动

### 方式一：Docker（推荐）

```bash
# 开发模式（热重载）
docker-compose up --build

# 生产模式
docker-compose -f docker-compose.prod.yml up --build
```

访问地址：
- 前端：http://localhost:5173
- 后端 API 文档：http://localhost:8000/docs

### 方式二：本地运行

**后端**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**前端**
```bash
cd frontend
npm install
npm run dev
```

## 目录结构

```
Insight/
├── backend/            FastAPI 后端
│   ├── main.py         入口 + 路由注册
│   ├── models.py       SQLModel 数据模型（7张表）
│   ├── database.py     SQLite 连接 + 种子数据
│   ├── schemas.py      Pydantic 请求/响应模型
│   ├── routers/        API 路由（targets / actuals / opportunities / dashboard / imports）
│   └── services/       导入服务（Excel/CSV 校验 + 写入）
│
├── frontend/           Vue 3 前端
│   ├── src/
│   │   ├── App.vue     侧边栏 + 顶部栏布局
│   │   ├── router/     Vue Router
│   │   ├── stores/     Pinia 全局状态
│   │   ├── api/        axios API 封装
│   │   └── views/      8个页面组件
│   └── nginx.conf      生产模式 nginx 配置
│
├── prototype/          原始 HTML 原型（设计参考）
├── PRD-经营分析系统-V1.0.md
├── docker-compose.yml         开发环境
└── docker-compose.prod.yml    生产环境
```

## 数据导入

系统支持通过 Excel/CSV 文件批量导入三类数据：

| 模板 | 必填字段 |
|------|---------|
| 年度目标 | 年份、事业部、指标类型、年度目标值 |
| 月度完成 | 年份、月份、事业部、指标类型、完成值 |
| 商机数据 | 商机名称、所属事业部、指标类型、所属年度、所属季度、预计金额（万元）、商机阶段、商机状态 |

- 支持 `.xlsx` / `.xls` / `.csv`（UTF-8）
- 月度完成数据：同组合重复导入覆盖写入
- 导入结果提供失败行详情，可在「月度数据导入」页查看

## Git 工作流

```bash
git init                          # 已初始化
git remote add origin <你的仓库地址>
git add .
git commit -m "feat: initial full-stack scaffold"
git push -u origin main
```

## 主要 API

| 接口 | 说明 |
|------|------|
| GET /api/dashboard/overview | 总览仪表盘（YTD完成率 + 同比增长） |
| GET /api/dashboard/division/{id} | 事业部详情（月度趋势 + 缺口分析） |
| GET /api/dashboard/opportunity-support | 商机支撑分析 |
| GET /api/dashboard/trend | 同比趋势分析 |
| POST /api/import/actuals | 上传月度完成数据 |
| POST /api/import/opportunities | 上传商机数据 |
| GET /api/import/history | 导入历史记录 |
