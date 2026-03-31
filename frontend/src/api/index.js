import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api', timeout: 30000 })

http.interceptors.response.use(
  res => res.data,
  err => {
    const msg = err.response?.data?.message || err.response?.data?.detail || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(err)
  }
)

// ── Dashboard ────────────────────────────────────────
export const getOverview      = (year) => http.get('/dashboard/overview', { params: { year } })
export const getDivisionDetail= (id, year) => http.get(`/dashboard/division/${id}`, { params: { year } })
export const getOppSupport    = (year, quarter) => http.get('/dashboard/opportunity-support', { params: { year, quarter } })
export const getTrend         = (metric) => http.get('/dashboard/trend', { params: { metric } })
export const getUnits         = () => http.get('/dashboard/units')
export const getQuarterly     = (year, quarter) => http.get('/dashboard/quarterly', { params: { year, quarter } })
export const getMonthly       = (year, month) => http.get('/dashboard/monthly', { params: { year, month } })

// ── Targets ──────────────────────────────────────────
export const getTargets       = (year) => http.get(`/targets/${year}`)
export const updateTargets    = (year, data) => http.put(`/targets/${year}`, data)
export const getChangelog     = (year) => http.get(`/targets/${year}/changelog`)

// ── Actuals ──────────────────────────────────────────
export const getActuals       = (params) => http.get('/actuals/', { params })
export const updateActual     = (id, amount) => http.put(`/actuals/${id}`, null, { params: { amount } })
export const deleteActual     = (id) => http.delete(`/actuals/${id}`)

// ── Opportunities ────────────────────────────────────
export const getOpportunities = (params) => http.get('/opportunities/', { params })
export const createOpportunity= (data) => http.post('/opportunities/', data)
export const updateOpportunity= (id, data) => http.put(`/opportunities/${id}`, data)
export const deleteOpportunity= (id) => http.delete(`/opportunities/${id}`)

// ── Import ───────────────────────────────────────────
export const importTargets    = (file) => _upload('/import/targets', file)
export const importActuals    = (file) => _upload('/import/actuals', file)
export const importOpps       = (file) => _upload('/import/opportunities', file)
export const getImportHistory = () => http.get('/import/history')
export const getBatchFailures = (id) => http.get(`/import/history/${id}/failures`)

function _upload(url, file) {
  const fd = new FormData()
  fd.append('file', file)
  return http.post(url, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}
