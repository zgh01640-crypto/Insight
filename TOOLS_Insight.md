# Insight 经营分析系统 — HTTP API 工具手册

openclaw 可通过 `exec` 直接执行以下命令访问系统。

## 基础信息

| 项目 | 值 |
|---|---|
| Base URL | `http://localhost:8010` |
| 响应格式 | `{"success": bool, "message": str, "data": any}` |
| 交互式文档 | `http://localhost:8010/docs`（Swagger UI） |
| 数量单位 | 万元 |

## 认证

系统支持可选的 API Key 认证（通过环境变量 `SYSTEM_API_KEY` 配置）。

- **内部前端**（localhost:5173 浏览器访问）：**无需认证**，自动豁免
- **外部调用**（curl / PowerShell / openclaw）：需在请求头加入 `X-API-Key`

```bash
# curl（需认证时）
curl -H "X-API-Key: your_key_here" "http://localhost:8010/api/dashboard/overview?year=2026"

# PowerShell（需认证时）
Invoke-RestMethod -Headers @{"X-API-Key"="your_key_here"} -Uri "http://localhost:8010/api/dashboard/overview?year=2026"
```

> 若未配置 `SYSTEM_API_KEY`，所有请求均无需认证（默认开放）。

**事业部 ID 映射：**
- `1` = 智能建造事业部
- `2` = 大数据事业部
- `3` = 数字交易事业部
- `4` = 智慧政务事业部

**指标类型：** `contract`（合同）/ `revenue`（收入）/ `payment`（回款）

---

## 健康检查

```bash
# curl
curl -s http://localhost:8010/api/health

# PowerShell
Invoke-RestMethod -Uri "http://localhost:8010/api/health"
```

**返回示例：** `{"status":"ok"}`

---

## 看板分析

### 年度仪表盘（所有事业部 YTD 达成率）

```bash
curl -s "http://localhost:8010/api/dashboard/overview?year=2026"
Invoke-RestMethod -Uri "http://localhost:8010/api/dashboard/overview?year=2026"
```

| 参数 | 说明 | 必填 |
|---|---|---|
| `year` | 年份 | 否（默认当年） |

---

### 单事业部详情

```bash
curl -s "http://localhost:8010/api/dashboard/division/1?year=2026"
Invoke-RestMethod -Uri "http://localhost:8010/api/dashboard/division/1?year=2026"
```

| 参数 | 说明 | 必填 |
|---|---|---|
| `{id}` | 事业部ID（路径参数，1-4） | 是 |
| `year` | 年份 | 否 |

---

### 季度仪表盘

```bash
curl -s "http://localhost:8010/api/dashboard/quarterly?year=2026&quarter=Q1"
Invoke-RestMethod -Uri "http://localhost:8010/api/dashboard/quarterly?year=2026&quarter=Q1"
```

| 参数 | 说明 | 必填 |
|---|---|---|
| `year` | 年份 | 否 |
| `quarter` | 季度，Q1/Q2/Q3/Q4 | 否（默认当季） |

---

### 月度仪表盘

```bash
curl -s "http://localhost:8010/api/dashboard/monthly?year=2026&month=3"
Invoke-RestMethod -Uri "http://localhost:8010/api/dashboard/monthly?year=2026&month=3"
```

| 参数 | 说明 | 必填 |
|---|---|---|
| `year` | 年份 | 否 |
| `month` | 月份（1-12） | 否（默认当月） |

---

### 商机支撑分析

```bash
curl -s "http://localhost:8010/api/dashboard/opportunity-support?year=2026&quarter=Q1"
Invoke-RestMethod -Uri "http://localhost:8010/api/dashboard/opportunity-support?year=2026&quarter=Q1"
```

---

### 事业部列表

```bash
curl -s "http://localhost:8010/api/dashboard/units"
Invoke-RestMethod -Uri "http://localhost:8010/api/dashboard/units"
```

---

## 商机

### 商机列表（支持多维度筛选）

```bash
curl -s "http://localhost:8010/api/opportunities/?year=2026&quarter=Q1"
Invoke-RestMethod -Uri "http://localhost:8010/api/opportunities/?year=2026&quarter=Q1"
```

| 参数 | 说明 | 可选值 |
|---|---|---|
| `year` | 年份 | 整数 |
| `quarter` | 季度 | Q1/Q2/Q3/Q4 |
| `business_unit_id` | 事业部ID | 1-4 |
| `metric_type` | 指标类型 | contract/revenue/payment |
| `stage` | 商机阶段 | 线索/立项/报价/签约跟进/已完成 |
| `status` | 商机状态 | 进行中/已赢单/已输单/已搁置 |

---

## 催收项目

### 催收仪表盘（汇总 + 事业部聚合 + Top10）

```bash
curl -s "http://localhost:8010/api/collections/dashboard?year=2026"
Invoke-RestMethod -Uri "http://localhost:8010/api/collections/dashboard?year=2026"
```

---

### 催收明细列表

```bash
curl -s "http://localhost:8010/api/collections/?year=2026&status=%E5%82%AC%E6%94%B6%E4%B8%AD"
Invoke-RestMethod -Uri "http://localhost:8010/api/collections/?year=2026&status=催收中"
```

| 参数 | 说明 | 可选值 |
|---|---|---|
| `year` | 年份 | 整数 |
| `business_unit_id` | 事业部ID | 1-4 |
| `status` | 状态 | 催收中/已回款/已核销 |

---

## 月度完成数据

```bash
curl -s "http://localhost:8010/api/actuals/?year=2026&month=3"
Invoke-RestMethod -Uri "http://localhost:8010/api/actuals/?year=2026&month=3"
```

| 参数 | 说明 |
|---|---|
| `year` | 年份 |
| `month` | 月份（1-12） |
| `business_unit_id` | 事业部ID（1-4） |

---

## 年度目标

```bash
curl -s "http://localhost:8010/api/targets/2026"
Invoke-RestMethod -Uri "http://localhost:8010/api/targets/2026"
```

---

## 响应格式说明

所有接口统一返回：

```json
{
  "success": true,
  "message": "",
  "data": { ... }
}
```

失败时：

```json
{
  "success": false,
  "message": "错误说明",
  "data": null
}
```

---

## 完整 API 文档

访问 Swagger UI 查看所有接口的完整参数和响应结构：

```
http://localhost:8010/docs
```
