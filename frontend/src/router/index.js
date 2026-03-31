import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/',            redirect: '/overview' },
  { path: '/overview',    component: () => import('@/views/Overview.vue'),          meta: { title: '年度仪表盘' } },
  { path: '/quarter',     component: () => import('@/views/QuarterDashboard.vue'), meta: { title: '季度仪表盘' } },
  { path: '/monthly',     component: () => import('@/views/MonthlyDashboard.vue'), meta: { title: '月度仪表盘' } },
  { path: '/division/:id',component: () => import('@/views/Division.vue'),          meta: { title: '事业部详情' } },
  { path: '/opportunity', component: () => import('@/views/Opportunity.vue'), meta: { title: '商机支撑分析' } },
  { path: '/trend',       component: () => import('@/views/Trend.vue'),       meta: { title: '同比趋势分析' } },
  { path: '/targets',     component: () => import('@/views/Targets.vue'),     meta: { title: '年度目标管理' } },
  { path: '/actuals',     component: () => import('@/views/Actuals.vue'),     meta: { title: '月度数据导入' } },
  { path: '/oppmgmt',     component: () => import('@/views/OppMgmt.vue'),     meta: { title: '商机管理' } },
  { path: '/settings',    component: () => import('@/views/Settings.vue'),    meta: { title: '设置 & 模板' } },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
