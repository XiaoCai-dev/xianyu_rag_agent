/** 仪表盘页面：核心指标 + 意图分布 + 7天趋势。 */
import { api } from '../api.js';

export default {
  template: `
    <div v-loading="loading">
      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="4" v-for="card in cards" :key="card.label">
          <el-card shadow="hover" class="stat-card">
            <div class="num">{{ card.value }}</div>
            <div class="label">{{ card.label }}</div>
          </el-card>
        </el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="10">
          <el-card header="意图分布" shadow="never">
            <div v-if="intents.length===0" style="color:#999;text-align:center;padding:20px">暂无数据</div>
            <div v-for="it in intents" :key="it.intent" style="display:flex;align-items:center;margin-bottom:10px">
              <span style="width:70px;font-size:13px">{{ it.intent }}</span>
              <el-progress :percentage="pct(it.n)" :format="()=>it.n" style="flex:1" />
            </div>
          </el-card>
        </el-col>
        <el-col :span="14">
          <el-card header="近7天消息趋势" shadow="never">
            <div v-if="trend.length===0" style="color:#999;text-align:center;padding:20px">暂无数据</div>
            <div v-else style="display:flex;align-items:flex-end;height:180px;gap:6px;padding:0 10px">
              <div v-for="d in trend" :key="d.day" style="flex:1;text-align:center">
                <div :style="{height:barHeight(d.n)+'px',background:'#409eff',borderRadius:'3px',marginBottom:'6px',minHeight:'2px'}"></div>
                <div style="font-size:11px;color:#909399">{{ d.day.slice(5) }}</div>
                <div style="font-size:12px;font-weight:600">{{ d.n }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  `,
  data() {
    return { loading: true, data: {}, maxTrend: 1 };
  },
  computed: {
    cards() {
      const d = this.data;
      return [
        { label: '今日消息', value: d.today_messages ?? 0 },
        { label: '总消息', value: d.total_messages ?? 0 },
        { label: '会话数', value: d.total_conversations ?? 0 },
        { label: '商品数', value: d.total_items ?? 0 },
        { label: 'Bot回复', value: d.bot_replies ?? 0 },
        { label: '议价会话', value: d.bargain_conversations ?? 0 },
      ];
    },
    intents() { return this.data.intent_distribution || []; },
    trend() {
      const t = this.data.trend_7d || [];
      this.maxTrend = Math.max(1, ...t.map(x => x.n));
      return t;
    },
  },
  methods: {
    pct(n) {
      const total = (this.data.intent_distribution || []).reduce((s, x) => s + x.n, 0) || 1;
      return Math.round(n / total * 100);
    },
    barHeight(n) { return Math.round(n / this.maxTrend * 150); },
    async load() {
      this.loading = true;
      try { this.data = await api.dashboard(); }
      catch (e) { this.$message.error('加载失败: ' + e.message); }
      finally { this.loading = false; }
    },
  },
  mounted() { this.load(); },
};
