/** 提示词管理页面：四个 prompt 在线编辑 + 保存触发热更新。 */
import { api } from '../api.js';

export default {
  template: `
    <div v-loading="loading">
      <el-tabs v-model="active" @tab-change="onTabChange">
        <el-tab-pane v-for="k in keys" :key="k" :label="labels[k]" :name="k" />
      </el-tabs>
      <el-input type="textarea" v-model="content" :rows="18"
               :placeholder="'正在加载 ' + labels[active]" style="font-family:monospace;font-size:13px" />
      <div style="margin-top:12px;display:flex;align-items:center;gap:12px">
        <el-button type="primary" :loading="saving" @click="save">保存并热更新</el-button>
        <el-button @click="load">重新加载</el-button>
        <el-checkbox v-model="reload">保存后触发热更新</el-checkbox>
      </div>
    </div>
  `,
  data() {
    return { loading: false, saving: false,
             keys: ['classify', 'price', 'tech', 'default'],
             labels: { classify: '意图分类', price: '价格专家', tech: '技术专家', default: '默认回复' },
             active: 'classify', content: '', reload: true };
  },
  methods: {
    async load() {
      this.loading = true;
      try {
        const all = await api.listPrompts();
        this._cache = all;
        this.content = all[this.active]?.content || '';
      } catch (e) { this.$message.error(e.message); }
      finally { this.loading = false; }
    },
    onTabChange() {
      this.content = this._cache?.[this.active]?.content || '';
    },
    async save() {
      this.saving = true;
      try {
        const r = await api.updatePrompt(this.active, this.content, this.reload);
        this.$message.success(r.message || '已保存');
      } catch (e) { this.$message.error(e.message); }
      finally { this.saving = false; }
    },
  },
  mounted() { this.load(); },
};
