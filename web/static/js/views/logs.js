/** 运行日志页面：分源查看 bot / web 进程日志，支持自动刷新、级别与关键字过滤。 */
import { api } from '../api.js';

export default {
  template: `
    <div>
      <el-card shadow="never" style="margin-bottom:16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
            <span>运行日志</span>
            <div style="display:flex;align-items:center;gap:12px">
              <el-tag v-if="sources.length" size="small" :type="activeSource?.exists ? 'success' : 'info'">
                {{ activeSource?.exists ? '已就绪' : '文件未生成' }}
              </el-tag>
              <el-switch v-model="autoRefresh" active-text="自动刷新" />
            </div>
          </div>
        </template>

        <el-form :inline="true" size="small">
          <el-form-item label="日志源">
            <el-radio-group v-model="source" @change="onSourceChange">
              <el-radio-button v-for="s in sources" :key="s.key" :value="s.key">
                {{ s.label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="级别">
            <el-select v-model="level" style="width:130px" @change="load">
              <el-option label="全部" value="" />
              <el-option label="DEBUG 及以上" value="DEBUG" />
              <el-option label="INFO 及以上" value="INFO" />
              <el-option label="WARNING 及以上" value="WARNING" />
              <el-option label="ERROR 及以上" value="ERROR" />
            </el-select>
          </el-form-item>
          <el-form-item label="行数">
            <el-select v-model="lines" style="width:100px" @change="load">
              <el-option :value="100" label="100" />
              <el-option :value="300" label="300" />
              <el-option :value="500" label="500" />
              <el-option :value="1000" label="1000" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键字">
            <el-input v-model="keyword" placeholder="过滤关键字" style="width:180px"
                      clearable @keyup.enter="load" @clear="load" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
            <el-button @click="copy">复制</el-button>
            <el-button :disabled="!activeSource?.exists" @click="download">下载</el-button>
            <el-button type="danger" plain @click="clear">清空</el-button>
          </el-form-item>
        </el-form>

        <div style="font-size:12px;color:#909399;display:flex;gap:16px;flex-wrap:wrap">
          <span>文件：{{ activeSource?.path || '-' }}</span>
          <span v-if="activeSource?.exists">大小：{{ humanSize(activeSource.size) }}</span>
          <span v-if="lastUpdated">更新于 {{ lastUpdated }}</span>
          <span v-if="count !== null">命中 {{ count }} 行</span>
        </div>
      </el-card>

      <el-alert v-if="notice" :title="notice" type="info" :closable="false" show-icon style="margin-bottom:12px" />

      <div class="log-view" v-loading="loading">
        <template v-if="rows.length">
          <div v-for="(r, i) in rows" :key="i" class="log-line">
            <span class="log-time">{{ (r.time || '').replace(/^\\d{4}-/, '') }}</span>
            <span class="log-level" :class="'lv-' + (r.level || 'PLAIN')">{{ r.level || '—' }}</span>
            <span class="log-msg">{{ r.message }}</span>
          </div>
        </template>
        <div v-else-if="!loading" class="log-empty">
          {{ activeSource?.exists ? '当前过滤条件下没有日志' : '日志文件尚未生成，请先启动对应进程（python main.py）' }}
        </div>
      </div>
    </div>
  `,
  data() {
    return {
      loading: false, sources: [], source: 'bot',
      level: '', keyword: '', lines: 300,
      rows: [], count: null, notice: '', lastUpdated: '',
      autoRefresh: false, timer: null,
    };
  },
  computed: {
    activeSource() { return this.sources.find(s => s.key === this.source); },
  },
  methods: {
    humanSize(n) {
      if (n === null || n === undefined) return '-';
      if (n < 1024) return n + ' B';
      if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
      return (n / 1024 / 1024).toFixed(2) + ' MB';
    },
    async loadSources() {
      try {
        const r = await api.logSources();
        this.sources = r.sources || [];
      } catch (e) { this.$message.error(e.message); }
    },
    async load() {
      this.loading = true;
      try {
        const r = await api.readLogs(this.source, this.lines, this.level, this.keyword);
        this.rows = r.lines || [];
        this.count = r.count ?? null;
        this.notice = r.exists ? '' : (r.message || '');
        this.lastUpdated = new Date().toLocaleTimeString('zh-CN');
        await this.loadSources();
      } catch (e) {
        this.notice = '读取日志失败：' + e.message;
      } finally {
        this.loading = false;
      }
    },
    onSourceChange() { this.load(); },
    async clear() {
      try { await this.$confirm('确认清空当前日志文件？', '提示', { type: 'warning' }); }
      catch (_) { return; }
      try {
        const r = await api.clearLogs(this.source);
        this.$message.success(r.cleared ? '已清空' : (r.message || '日志文件不存在'));
        await this.load();
      } catch (e) { this.$message.error(e.message); }
    },
    copy() {
      const text = this.rows.map(r =>
        r.time ? `${r.time} | ${r.level.padEnd(8)} | ${r.message}` : r.message).join('\n');
      navigator.clipboard.writeText(text)
        .then(() => this.$message.success('已复制到剪贴板'))
        .catch(() => this.$message.error('复制失败'));
    },
    download() { window.open(api.logDownloadUrl(this.source), '_blank'); },
    startTimer() {
      this.stopTimer();
      this.timer = setInterval(() => this.load(), 2000);
    },
    stopTimer() { if (this.timer) { clearInterval(this.timer); this.timer = null; } },
  },
  watch: {
    autoRefresh(v) { v ? this.startTimer() : this.stopTimer(); },
  },
  mounted() { this.loadSources(); this.load(); },
  unmounted() { this.stopTimer(); },
};
