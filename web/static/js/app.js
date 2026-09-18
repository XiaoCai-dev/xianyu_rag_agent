/** 主应用：布局 + hash 路由 + 页面注册。 */
import { createApp, ref, computed, onMounted } from 'vue';
import ElementPlus from 'element-plus';

import Dashboard from './views/dashboard.js';
import Conversations from './views/conversations.js';
import Rag from './views/rag.js';
import Prompts from './views/prompts.js';
import Config from './views/config.js';
import Logs from './views/logs.js';

const PAGES = {
  dashboard: { label: '仪表盘', comp: Dashboard },
  conversations: { label: '会话浏览', comp: Conversations },
  rag: { label: '知识库', comp: Rag },
  prompts: { label: '提示词', comp: Prompts },
  config: { label: '配置管理', comp: Config },
  logs: { label: '运行日志', comp: Logs },
};

const App = {
  setup() {
    const route = ref(location.hash.slice(1) || 'dashboard');
    const onHash = () => { route.value = location.hash.slice(1) || 'dashboard'; };
    window.addEventListener('hashchange', onHash);
    onMounted(onHash);

    const go = (k) => { location.hash = k; };
    const current = computed(() => PAGES[route.value] || PAGES.dashboard);

    return { PAGES, route, current, go };
  },
  template: `
    <div class="layout">
      <div class="sidebar">
        <div class="logo">闲鱼 RAG Agent</div>
        <el-menu :default-active="route" @select="go">
          <el-menu-item v-for="(p,k) in PAGES" :key="k" :index="k">
            <span>{{ p.label }}</span>
          </el-menu-item>
        </el-menu>
      </div>
      <div class="main">
        <div class="header">{{ current.label }}</div>
        <div class="content">
          <component :is="current.comp" />
        </div>
      </div>
    </div>
  `,
};

createApp(App).use(ElementPlus).mount('#app');
