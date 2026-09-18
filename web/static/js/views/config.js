/** 配置管理页面：LLM配置 / Embedding配置 / 闲鱼接入 / 行为设置 + 一键连通性自检 */
import { api } from '../api.js';

export default {
  template: `
    <div v-loading="loading" style="max-width:760px">
      <!-- 自检结果 -->
      <el-card shadow="never" style="margin-bottom:16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
            <span>🩺 配置自检</span>
            <div style="display:flex;gap:8px">
              <el-button size="small" :loading="testing.llm" @click="test(['llm'])">测试对话模型</el-button>
              <el-button size="small" :loading="testing.embedding" @click="test(['embedding'])">测试向量模型</el-button>
              <el-button size="small" :loading="testing.cookie" @click="test(['cookie'])">测试 Cookie</el-button>
              <el-button size="small" type="primary" plain :loading="testingAll" @click="test(['llm','embedding','cookie'])">
                全部检测
              </el-button>
            </div>
          </div>
        </template>
        <el-alert v-if="!results.length" type="info" :closable="false" show-icon
                  title="修改配置并保存后，建议先跑一次自检，确认模型与 Cookie 真正可用。" />
        <div v-else>
          <el-alert v-for="r in results" :key="r.target" :type="r.ok ? 'success' : 'error'"
                    :title="labelOf(r.target) + (r.ok ? ' 正常' : ' 失败')" :closable="false" show-icon
                    style="margin-bottom:8px">
            <div style="font-size:12.5px;line-height:1.7">
              {{ r.detail }}
              <span v-if="r.latency_ms">（{{ r.latency_ms }} ms）</span>
              <span v-if="r.sample">｜样例回复：{{ r.sample }}</span>
              <span v-if="r.model">｜模型：{{ r.model }}</span>
              <span v-if="r.provider">｜后端：{{ r.provider }}</span>
            </div>
          </el-alert>
        </div>
      </el-card>

      <!-- LLM 配置 -->
      <el-card shadow="never" style="margin-bottom:16px">
        <template #header>🧠 LLM 对话模型</template>
        <el-form label-width="160px" size="default">
          <el-form-item label="LLM API Key">
            <el-input v-model="form.API_KEY" :type="showKey?'text':'password'" placeholder="LLM 供应商的 API Key">
              <template #append><el-button @click="showKey=!showKey">{{ showKey?'隐藏':'显示' }}</el-button></template>
            </el-input>
          </el-form-item>
          <el-form-item label="LLM 地址">
            <el-input v-model="form.MODEL_BASE_URL" placeholder="https://apihub.agnes-ai.com/v1" />
          </el-form-item>
          <el-form-item label="LLM 模型名称">
            <el-input v-model="form.MODEL_NAME" placeholder="agnes-3.0-flash" />
          </el-form-item>
        </el-form>
      </el-card>

      <!-- Embedding 配置 -->
      <el-card shadow="never" style="margin-bottom:16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>📐 向量模型（RAG 检索用）</span>
            <el-text type="info" size="small">选「本地内置模型」则完全离线，无需 Key</el-text>
          </div>
        </template>
        <el-form label-width="160px" size="default">
          <el-form-item label="向量模型来源">
            <el-select v-model="form.EMBEDDING_PROVIDER" style="width:100%">
              <el-option v-for="o in providerOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.EMBEDDING_PROVIDER !== 'local' && form.EMBEDDING_PROVIDER !== 'off'"
                        label="Embedding API Key">
            <el-input v-model="form.EMBEDDING_API_KEY" :type="showEKey?'text':'password'"
                      placeholder="如使用阿里云百炼，填 DashScope 的 Key">
              <template #append><el-button @click="showEKey=!showEKey">{{ showEKey?'隐藏':'显示' }}</el-button></template>
            </el-input>
            <el-text type="warning" size="small" style="margin-top:4px">
              注意：对话模型供应商若不提供 /embeddings 接口，需另填一家向量模型的 Key。
            </el-text>
          </el-form-item>
          <template v-if="form.EMBEDDING_PROVIDER !== 'local' && form.EMBEDDING_PROVIDER !== 'off'">
            <el-form-item label="Embedding 地址">
              <el-input v-model="form.EMBEDDING_BASE_URL"
                        placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
            </el-form-item>
            <el-form-item label="Embedding 模型">
              <el-input v-model="form.EMBEDDING_MODEL" placeholder="text-embedding-v3" />
            </el-form-item>
          </template>
          <el-form-item label="相关度阈值">
            <el-input v-model="form.RAG_MAX_DISTANCE" placeholder="留空则自动" style="width:140px" />
            <el-text type="info" size="small" style="margin-left:8px">
              余弦距离，越小越严格；本地模型建议 0.75，在线模型 0.6
            </el-text>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 闲鱼接入 -->
      <el-card shadow="never" style="margin-bottom:16px">
        <template #header>🍪 闲鱼接入</template>
        <el-form label-width="160px" size="default">
          <el-form-item label="Cookie">
            <el-input v-model="form.COOKIES_STR" :type="showCookie?'text':'password'"
                      placeholder="闲鱼网页端获取的 Cookie" />
            <div style="margin-top:4px">
              <el-button text size="small" @click="showCookie=!showCookie">{{ showCookie?'隐藏':'显示' }} Cookie</el-button>
              <el-text type="info" size="small" style="margin-left:8px">浏览器打开 goofish.com → F12 → Network → 复制 Cookie</el-text>
            </div>
          </el-form-item>
          <el-form-item label="人工接管关键词">
            <el-input v-model="form.TOGGLE_KEYWORDS" placeholder="。" style="width:200px" />
            <el-text type="info" size="small">输入此词切换人工/AI接管</el-text>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 行为设置 -->
      <el-card shadow="never" style="margin-bottom:16px">
        <template #header>⚙️ 行为设置</template>
        <el-form label-width="160px" size="default">
          <el-form-item label="模拟人工输入">
            <el-switch v-model="form.SIMULATE_HUMAN_TYPING" active-value="True" inactive-value="False" />
          </el-form-item>
          <el-form-item label="控制轮询间隔">
            <el-input v-model="form.CONTROL_POLL_INTERVAL" placeholder="10" style="width:120px">
              <template #append>秒</template>
            </el-input>
          </el-form-item>
          <el-form-item label="日志级别">
            <el-select v-model="form.LOG_LEVEL" style="width:140px">
              <el-option label="DEBUG" value="DEBUG" />
              <el-option label="INFO" value="INFO" />
              <el-option label="WARNING" value="WARNING" />
              <el-option label="ERROR" value="ERROR" />
            </el-select>
            <el-text type="info" size="small" style="margin-left:8px">修改后需重启 Bot，可在「运行日志」查看</el-text>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 保存 -->
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <el-button type="primary" size="large" :loading="saving" @click="save">保存配置并重启 Bot</el-button>
        <el-button size="large" @click="load">重新加载</el-button>
        <el-checkbox v-model="restart">保存后重启 Bot</el-checkbox>
      </div>
      <div v-if="envPath" style="margin-top:10px">
        <el-text type="info" size="small">配置文件：{{ envPath }}</el-text>
      </div>
    </div>
  `,
  data() {
    return {
      loading: false, saving: false, testingAll: false,
      showKey: false, showEKey: false, showCookie: false, restart: true,
      results: [], testing: {}, envPath: '',
      providerOptions: [
        { value: 'auto', label: '自动（填了 Key 用在线，否则用本地内置）' },
        { value: 'local', label: '本地内置模型（离线，无需 Key）' },
        { value: 'api', label: '在线接口（需填 Embedding API Key）' },
        { value: 'off', label: '关闭向量检索' },
      ],
      form: {
        API_KEY: '', MODEL_BASE_URL: '', MODEL_NAME: '',
        EMBEDDING_PROVIDER: 'auto',
        EMBEDDING_API_KEY: '', EMBEDDING_BASE_URL: '', EMBEDDING_MODEL: '',
        RAG_MAX_DISTANCE: '',
        COOKIES_STR: '',
        TOGGLE_KEYWORDS: '', SIMULATE_HUMAN_TYPING: 'False',
        CONTROL_POLL_INTERVAL: '', LOG_LEVEL: 'INFO',
      },
    };
  },
  methods: {
    labelOf(t) {
      return { llm: '对话模型', embedding: '向量模型', cookie: '闲鱼 Cookie' }[t] || t;
    },
    async load() {
      this.loading = true;
      try {
        const data = await api.getConfig();
        for (const k in this.form) {
          if (data[k]) this.form[k] = data[k].value;
        }
        if (data.EMBEDDING_PROVIDER?.options) this.providerOptions = data.EMBEDDING_PROVIDER.options;
      } catch (e) { this.$message.error(e.message); }
      finally { this.loading = false; }
    },
    async loadEnvPath() {
      try {
        const r = await fetch('/api/config/env-path').then(x => x.json());
        this.envPath = r.env_path || '';
      } catch (_) { /* 忽略 */ }
    },
    async save() {
      this.saving = true;
      try {
        const payload = { ...this.form, restart: this.restart };
        const r = await api.updateConfig(payload);
        if (r.updated && r.updated.length > 0) {
          this.$message.success(r.message || `已更新 ${r.updated.length} 项配置`);
        } else {
          this.$message.info('没有变更项（敏感字段需输入新值才会更新）');
        }
      } catch (e) { this.$message.error(e.message); }
      finally { this.saving = false; }
    },
    async test(targets) {
      const isAll = targets.length > 1;
      if (isAll) this.testingAll = true;
      targets.forEach(t => { this.testing[t] = true; });
      try {
        const r = await api.testConfig(targets);
        this.results = r.results || [];
        r.all_ok ? this.$message.success('全部检测通过') : this.$message.warning('部分检测未通过，详见结果');
      } catch (e) { this.$message.error(e.message); }
      finally {
        targets.forEach(t => { this.testing[t] = false; });
        this.testingAll = false;
      }
    },
  },
  mounted() { this.load(); this.loadEnvPath(); },
};
