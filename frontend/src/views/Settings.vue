<script setup>
const templates = [
  { name: '年度目标导入模板', desc: '批量设置年度目标及月度分解', type: 'targets' },
  { name: '月度完成数据导入模板', desc: '录入各事业部月度实际完成数据', type: 'actuals' },
  { name: '商机数据导入模板', desc: '批量录入商机明细', type: 'opps' },
]
const threshold = ref(60)

import { ref } from 'vue'
</script>

<template>
  <div>
    <div style="font-size:16px;font-weight:600;margin-bottom:16px">设置 &amp; 模板</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
      <div class="card">
        <div class="card-title">导入模板下载</div>
        <div style="display:flex;flex-direction:column;gap:10px">
          <div v-for="t in templates" :key="t.type" class="tmpl-row">
            <div>
              <div style="font-size:13px;font-weight:500;color:var(--text-pri)">{{ t.name }}</div>
              <div style="font-size:11px;color:var(--text-sec);margin-top:2px">{{ t.desc }}</div>
            </div>
            <a :href="`/api/import/template/${t.type}`" download>
              <el-button size="small">↓ 下载</el-button>
            </a>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-title">系统配置</div>
        <el-form label-width="120px" size="small">
          <el-form-item label="完成率预警阈值">
            <el-input-number v-model="threshold" :min="0" :max="100" />
            <span style="margin-left:8px;color:var(--text-sec)">%（当前：{{ threshold }}%）</span>
          </el-form-item>
          <el-form-item label="后端 API">
            <span style="font-family:var(--mono);color:var(--text-sec)">http://localhost:8010</span>
            <a href="http://localhost:8010/docs" target="_blank" style="margin-left:10px;color:var(--accent);font-size:12px">查看 API 文档 →</a>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:18px 20px; }
.card-title { font-size:11px; letter-spacing:1.5px; color:var(--text-sec); text-transform:uppercase; margin-bottom:14px; display:flex; align-items:center; gap:8px; }
.card-title::before { content:''; display:block; width:3px; height:12px; border-radius:2px; background:var(--accent); }
.tmpl-row { display:flex; align-items:center; justify-content:space-between; padding:10px 12px; background:var(--bg-base); border-radius:7px; border:1px solid var(--bg-border); }
</style>
