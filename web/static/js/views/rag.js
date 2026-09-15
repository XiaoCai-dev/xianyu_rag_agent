/** 知识库管理页面：文档列表、上传入库、删除、检索测试。 */
import { api } from '../api.js';

export default {
  template: `
    <div>
      <el-card shadow="never" style="margin-bottom:16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span>知识库管理</span>
            <el-tag size="small">向量 {{ stats.vector_count ?? '-' }} / 文档 {{ docs.length }}</el-tag>
          </div>
        </template>
        <el-form :inline="true" size="small">
          <el-form-item label="文件">
            <input type="file" ref="fileInput" accept=".txt,.md" />
          </el-form-item>
          <el-form-item label="范围">
            <el-select v-model="form.scope" style="width:110px">
              <el-option label="店铺通用" value="shop" />
              <el-option label="指定商品" value="item" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.scope==='item'" label="商品ID">
            <el-input v-model="form.item_id" placeholder="item_id" style="width:160px" />
          </el-form-item>
          <el-form-item label="标题">
            <el-input v-model="form.title" placeholder="可选" style="width:180px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="uploading" @click="ingest">入库</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never" style="margin-bottom:16px">
        <template #header>文档列表</template>
        <el-table :data="docs" v-loading="loading" size="small" stripe>
          <el-table-column prop="title" label="标题" min-width="160" />
          <el-table-column prop="scope" label="范围" width="100" />
          <el-table-column prop="item_id" label="商品ID" width="120">
            <template #default="{row}">{{ row.item_id || '-' }}</template>
          </el-table-column>
          <el-table-column prop="chunk_count" label="块数" width="80" />
          <el-table-column prop="source" label="来源" width="120" />
          <el-table-column label="操作" width="90">
            <template #default="{row}">
              <el-button type="danger" size="small" link @click="del(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>检索测试</template>
        <el-form :inline="true" size="small">
          <el-form-item label="查询">
            <el-input v-model="search.q" placeholder="输入测试问题" style="width:300px" @keyup.enter="doSearch" />
          </el-form-item>
          <el-form-item label="商品ID">
            <el-input v-model="search.item_id" placeholder="可选" style="width:140px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="doSearch" :loading="searching">检索</el-button>
          </el-form-item>
        </el-form>
        <el-input type="textarea" v-model="search.result" :rows="5" readonly
                  placeholder="检索结果将显示在此" style="margin-top:8px" />
      </el-card>
    </div>
  `,
  data() {
    return { loading: false, uploading: false, searching: false,
             docs: [], stats: {},
             form: { scope: 'shop', item_id: '', title: '' },
             search: { q: '', item_id: '', result: '' } };
  },
  methods: {
    async load() {
      this.loading = true;
      try { const r = await api.listRag(); this.docs = r.items; this.stats = r.stats; }
      catch (e) { this.$message.error(e.message); }
      finally { this.loading = false; }
    },
    async ingest() {
      const file = this.$refs.fileInput.files[0];
      if (!file) { this.$message.warning('请选择文件'); return; }
      if (this.form.scope === 'item' && !this.form.item_id) {
        this.$message.warning('商品范围需填写商品ID'); return;
      }
      this.uploading = true;
      try {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('scope', this.form.scope);
        fd.append('item_id', this.form.item_id);
        fd.append('title', this.form.title);
        const r = await api.ingestRag(fd);
        this.$message.success(`入库成功：${r.ingested_chunks} 个文本块`);
        this.form.title = '';
        this.$refs.fileInput.value = '';
        await this.load();
      } catch (e) { this.$message.error(e.message); }
      finally { this.uploading = false; }
    },
    async del(row) {
      try { await this.$confirm(`确认删除「${row.title}」？`, '提示', { type: 'warning' }); }
      catch (_) { return; }
      try { await api.deleteRag(row.doc_id); this.$message.success('已删除'); await this.load(); }
      catch (e) { this.$message.error(e.message); }
    },
    async doSearch() {
      if (!this.search.q.trim()) return;
      this.searching = true;
      try { const r = await api.searchRag(this.search.q, this.search.item_id);
            this.search.result = r.result || '（未命中知识库）'; }
      catch (e) { this.$message.error(e.message); }
      finally { this.searching = false; }
    },
  },
  mounted() { this.load(); },
};
