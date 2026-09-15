/** 会话浏览页面：左侧会话列表，右侧消息详情。 */
import { api } from '../api.js';

export default {
  template: `
    <div style="display:flex;gap:12px;height:100%">
      <div style="width:380px;flex-shrink:0;background:#fff;border-radius:8px;overflow:auto">
        <div style="padding:10px;border-bottom:1px solid #eee">
          <el-input v-model="keyword" placeholder="搜索会话" size="small" clearable />
        </div>
        <div v-loading="loadingList">
          <div v-for="c in filtered" :key="c.chat_id"
               @click="select(c.chat_id)"
               :class="['conv-item',{active:c.chat_id===activeId}]">
            <div style="font-weight:600;font-size:13px;margin-bottom:2px">
              {{ c.last_user_msg || c.chat_id }}
            </div>
            <div style="font-size:11px;color:#909399;display:flex;justify-content:space-between">
              <span>{{ c.msg_count }} 条</span>
              <span>{{ fmt(c.last_active) }}</span>
            </div>
          </div>
          <el-empty v-if="!loadingList && filtered.length===0" description="暂无会话" />
        </div>
        <div style="padding:8px;text-align:center">
          <el-pagination v-model="page" :page-size="20" :total="total" layout="prev,next"
                         @current-change="loadList" small />
        </div>
      </div>
      <div style="flex:1;background:#fff;border-radius:8px;display:flex;flex-direction:column;overflow:hidden">
        <div v-if="activeId" style="padding:10px 16px;border-bottom:1px solid #eee;font-size:13px;color:#606266">
          会话 {{ activeId }}
          <el-tag v-if="detail?.bargain_count>0" type="warning" size="small" style="margin-left:8px">
            议价 {{ detail.bargain_count }} 次
          </el-tag>
          <el-tag v-if="detail?.item" size="small" style="margin-left:8px">
            {{ detail.item.item_id }}
          </el-tag>
        </div>
        <div v-loading="loadingDetail" style="flex:1;overflow:auto;padding:16px;display:flex;flex-direction:column">
          <template v-if="detail">
            <div v-for="m in detail.messages" :key="m.id"
                 :class="['chat-bubble', m.role==='user'?'chat-user':'chat-bot']"
                 :style="m.role==='user'?'margin-left:auto':''">
              <el-tag v-if="m.intent" size="small" effect="plain" class="intent-tag" style="margin-right:6px">
                {{ m.intent }}
              </el-tag>
              {{ m.content }}
            </div>
          </template>
          <el-empty v-else-if="!loadingDetail" description="选择左侧会话查看详情" />
        </div>
      </div>
    </div>
  `,
  data() {
    return { loadingList: false, loadingDetail: false, list: [], total: 0, page: 1,
             activeId: null, detail: null, keyword: '' };
  },
  computed: {
    filtered() {
      if (!this.keyword) return this.list;
      const k = this.keyword.toLowerCase();
      return this.list.filter(c => (c.last_user_msg || c.chat_id || '').toLowerCase().includes(k));
    },
  },
  methods: {
    async loadList() {
      this.loadingList = true;
      try { const r = await api.listConversations(this.page); this.list = r.items; this.total = r.total; }
      catch (e) { this.$message.error(e.message); }
      finally { this.loadingList = false; }
    },
    async select(id) {
      this.activeId = id; this.loadingDetail = true;
      try { this.detail = await api.getConversation(id); }
      catch (e) { this.$message.error(e.message); }
      finally { this.loadingDetail = false; }
    },
    fmt(t) { if (!t) return ''; return String(t).slice(5, 16).replace('T', ' '); },
  },
  mounted() { this.loadList(); },
};
