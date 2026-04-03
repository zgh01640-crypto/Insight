<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { getUnits } from '@/api'
import AIChat from '@/components/AIChat.vue'

const route  = useRoute()
const store  = useAppStore()

const navItems = [
  { group: '看板', items: [
    { path: '/overview',             label: '年度仪表盘',    icon: 'DataAnalysis' },
    { path: '/quarter',              label: '季度仪表盘',    icon: 'Calendar' },
    { path: '/monthly',              label: '月度仪表盘',    icon: 'Histogram' },
    { path: '/opportunity',          label: '商机分析',      icon: 'TrendCharts' },
    { path: '/trend',                label: '同比趋势分析',  icon: 'DataLine' },
    { path: '/collection-dashboard', label: '催收仪表盘',    icon: 'Money' },
  ]},
  { group: '数据管理', items: [
    { path: '/targets',      label: '年度目标管理', icon: 'AimFilled' },
    { path: '/actuals',      label: '月度数据导入', icon: 'Upload' },
    { path: '/oppmgmt',      label: '商机管理',     icon: 'Opportunity' },
    { path: '/collections',  label: '催收项目管理', icon: 'CreditCard' },
  ]},
  { group: '系统', items: [
    { path: '/settings', label: '设置 & 模板', icon: 'Setting' },
  ]},
]

const years = [new Date().getFullYear(), new Date().getFullYear() - 1]

onMounted(async () => {
  const res = await getUnits()
  if (res?.data) store.setUnits(res.data)
})
</script>

<template>
  <div class="app">
    <!-- SIDEBAR -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <div class="logo-en">INSIGHT</div>
        <div class="logo-zh">经营分析智能体</div>
      </div>
      <nav class="sidebar-nav">
        <template v-for="group in navItems" :key="group.group">
          <div class="nav-label">{{ group.group }}</div>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: route.path === item.path || route.path.startsWith(item.path + '/') }"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            {{ item.label }}
          </router-link>
        </template>
      </nav>
      <div class="sidebar-footer">
        产品中心 · {{ new Date().getFullYear() }}
      </div>
    </aside>

    <!-- MAIN -->
    <div class="main">
      <header class="topbar">
        <div>
          <div class="topbar-title">{{ route.meta.title }}</div>
          <div class="topbar-sub">产品中心 · {{ store.units.length }} 个事业部</div>
        </div>
        <div class="topbar-right">
          <el-select
            v-model="store.year"
            size="small"
            style="width:110px"
            @change="store.setYear($event)"
          >
            <el-option v-for="y in years" :key="y" :label="`${y}年`" :value="y" />
          </el-select>
          <span class="status-dot" title="数据已更新" />
        </div>
      </header>
      <div class="content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </div>
    <AIChat />
  </div>
</template>

<style scoped>
.app { display: flex; height: 100vh; overflow: hidden; }

.sidebar {
  width: var(--sidebar-w); flex-shrink: 0;
  background: var(--bg-card);
  border-right: 1px solid var(--bg-border);
  display: flex; flex-direction: column;
}
.sidebar-logo { padding: 22px 20px 18px; border-bottom: 1px solid var(--bg-border); }
.logo-en { font-size: 26px; letter-spacing: 4px; color: var(--accent); font-weight: 800; line-height: 1; }
.logo-zh { font-size: 11px; color: var(--text-sec); letter-spacing: 2px; margin-top: 3px; }

.sidebar-nav { flex: 1; padding: 12px 0; overflow-y: auto; }
.nav-label { font-size: 10px; letter-spacing: 2px; color: var(--text-dim); padding: 12px 20px 4px; text-transform: uppercase; }
.nav-item {
  display: flex; align-items: center; gap: 9px;
  padding: 9px 20px; cursor: pointer;
  color: var(--text-sec); font-size: 13px; text-decoration: none;
  border-left: 2px solid transparent; transition: all .15s;
}
.nav-item:hover { color: var(--text-pri); background: var(--bg-hover); }
.nav-item.active { color: var(--accent); background: rgba(240,165,0,.07); border-left-color: var(--accent); }

.sidebar-footer { padding: 14px 20px; border-top: 1px solid var(--bg-border); color: var(--text-dim); font-size: 11px; }

.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.topbar {
  height: 52px; flex-shrink: 0; display: flex; align-items: center;
  padding: 0 24px; gap: 12px;
  background: var(--bg-card); border-bottom: 1px solid var(--bg-border);
}
.topbar-title { font-size: 15px; font-weight: 600; }
.topbar-sub { font-size: 12px; color: var(--text-sec); }
.topbar-right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 6px var(--green); display: inline-block; }

.content { flex: 1; overflow-y: auto; padding: 20px 24px; }

.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
