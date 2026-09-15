/** 配置管理页面：模型配置 / 闲鱼接入 / 行为设置，保存写 .env 并通知 bot 重启。 */
import { api } from '../api.js';

export default {
  template: `
    <div v-loading="loading" style="max-width:720px">
      <!-- 模型配置 -->
      <el-card shadow="never" style="margin-bottom:16px">
        <template #header>🤖 模型配置</template>
        <el-form label-width="140px" size="default">
          <el-form-item label="API Key">
            <el-input v-model="form.API_KEY" :type="showKey?'text':'password'" placeholder="百炼平台 API Key">
              <template #append>
                <el-button @click="showKey=!showKey">{{ showKey?'隐藏':'显示' }}</el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item label="模型地址">
            <el-input v-model="form.MODEL_BASE_URL" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
          </el-form-item>
          <el-form-item label="模型名称">
            <el-input v-model="form.MODEL_NAME" placeholder="qwen-max" />
          </el-form-item>
          <el-form-item label="Embedding 模型">
            <el-input v-model="form.EMBEDDING_MODEL" placeholder="text-embedding-v3" />
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 闲鱼接入 -->
      <el-card shadow="never" style="margin-bottom:16px">
        <template #header>🍪 闲鱼接入</template>
        <el-form label-width="140px" size="default">
          <el-form-item label="Cookie">
            <el-input v-model="form.COOKIES_STR" :type="showCookie?'text':'password'"
                      placeholder="闲鱼网页端获取的 Cookie" />
            <div style="margin-top:4px">
              <el-button text size="small" @click="showCookie=!showCookie">
                {{ showCookie?'隐藏':'显示' }} Cookie
              </el-button>
              <el-text type="info" size="small" style="margin-left:8px">
                浏览器打开 goofish.com → F12 → Network → 复制 Cookie
              </el-text>
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
        <el-form label-width="140px" size="default">
          <el-form-item label="模拟人工输入">
            <el-switch v-model="form.SIMULATE_HUMAN_TYPING" active-value="True" inactive-value="False" />
          </el-form-item>
          <el-form-item label="控制轮询间隔">
            <el-input v-model="form.CONTROL_POLL_INTERVAL" placeholder="10" style="width:120px">
              <template #append>秒</template>
            </el-input>
          </el-form-item>
          <el-form-item label="日志级别">
            <el-select v-model="form.LOG_LEVEL" style="width:120px">
              <el-option label="DEBUG" value="DEBUG" />
              <el-option label="INFO" value="INFO" />
              <el-option label="WARNING" value="WARNING" />
              <el-option label="ERROR" value="ERROR" />
            </el-select>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 保存 -->
      <div style="display:flex;gap:12px;align-items:center">
        <el-button type="primary" size="large" :loading="saving" @click="save">保存配置并重启 Bot</el-button>
        <el-button size="large" @click="load">重新加载</el-button>
        <el-checkbox v-model="restart">保存后重启 Bot</el-checkbox>
      </div>
    </div>
  `,
  data() {
    return {
      loading: false, saving: false,
      showKey: false, showCookie: false, restart: true,
      form: {
        API_KEY: '', MODEL_BASE_URL: '', MODEL_NAME: '',
        EMBEDDING_MODEL: '', COOKIES_STR: '',
        TOGGLE_KEYWORDS: '', SIMULATE_HUMAN_TYPING: 'False',
        CONTROL_POLL_INTERVAL: '', LOG_LEVEL: 'INFO',
      },
    };
  },
  methods: {
    async load() {
      this.loading = true;
      try {
        const data = await api.getConfig();
        for (const k in this.form) {
          if (data[k]) this.form[k] = data[k].value;
        }
      } catch (e) { this.$message.error(e.message); }
      finally { this.loading = false; }
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
  },
  mounted() { this.load(); },
};
