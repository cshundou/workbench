<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { Search } from '@element-plus/icons-vue';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import InstallConfirmDialog from '@/components/plugins/InstallConfirmDialog.vue';
import {
  installPlugin,
  listMarketplace,
  listPluginCategories,
  type PluginCategory,
  type PluginInfo,
} from '@/api/plugins';

const router = useRouter();
const loading = ref(false);
const installDialogVisible = ref(false);
const installing = ref(false);
const pendingPlugin = ref<PluginInfo | null>(null);
const plugins = ref<PluginInfo[]>([]);
const categories = ref<PluginCategory[]>([]);
const activeCategory = ref('');
const keyword = ref('');
const total = ref(0);
const featuredPlugins = ref<PluginInfo[]>([]);
const showFeatured = ref(true);

async function fetchData(): Promise<void> {
  loading.value = true;
  try {
    const [cats, result, featured] = await Promise.all([
      listPluginCategories(),
      listMarketplace({
        category: activeCategory.value || undefined,
        keyword: keyword.value || undefined,
        page: 1,
        page_size: 24,
      }),
      listMarketplace({ featured_only: true, page: 1, page_size: 8 }),
    ]);
    categories.value = cats;
    plugins.value = result.items;
    total.value = result.total;
    featuredPlugins.value = featured.items;
  } finally {
    loading.value = false;
  }
}

function openInstall(plugin: PluginInfo): void {
  if (plugin.is_installed) {
    ElMessage.info('插件已安装');
    return;
  }
  pendingPlugin.value = plugin;
  installDialogVisible.value = true;
}

async function confirmInstall(): Promise<void> {
  if (!pendingPlugin.value) return;
  installing.value = true;
  try {
    await installPlugin(pendingPlugin.value.plugin_id);
    ElMessage.success(`${pendingPlugin.value.name} 安装成功`);
    installDialogVisible.value = false;
    fetchData();
  } finally {
    installing.value = false;
  }
}

function goDetail(plugin: PluginInfo): void {
  router.push({ name: 'PluginDetail', params: { pluginId: plugin.plugin_id } });
}

watch(activeCategory, fetchData);

onMounted(fetchData);
</script>

<template>
  <div class="marketplace">
    <SectionHeader title="插件市场" description="发现与安装官方及第三方插件，扩展 Agent 能力" />
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索插件..."
        clearable
        class="search-input"
        @keyup.enter="fetchData"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="fetchData">搜索</el-button>
      <el-button @click="router.push({ name: 'PluginsInstalled' })">已安装</el-button>
      <el-button @click="router.push({ name: 'SkillsConfig' })">技能配置</el-button>
    </div>
    <section v-if="showFeatured && featuredPlugins.length && !keyword && !activeCategory" class="featured">
      <h2 class="section-title">官方推荐</h2>
      <div class="featured-grid">
        <div
          v-for="plugin in featuredPlugins"
          :key="plugin.plugin_id"
          class="plugin-card featured-card"
          @click="goDetail(plugin)"
        >
          <el-tag size="small" type="warning">推荐</el-tag>
          <div class="card-header">
            <span class="icon">{{ plugin.icon || '🔌' }}</span>
            <div>
              <h3>{{ plugin.name }}</h3>
              <p class="author">⭐ {{ plugin.rating_avg.toFixed(1) }}</p>
            </div>
          </div>
          <p class="desc">{{ plugin.description }}</p>
        </div>
      </div>
    </section>
    <div class="layout">
      <aside class="sidebar">
        <button
          class="cat-item"
          :class="{ active: !activeCategory }"
          @click="activeCategory = ''"
        >
          全部插件
        </button>
        <button
          v-for="cat in categories"
          :key="cat.key"
          class="cat-item"
          :class="{ active: activeCategory === cat.key }"
          @click="activeCategory = cat.key"
        >
          {{ cat.label }}
        </button>
      </aside>
      <div v-loading="loading" class="grid">
        <div
          v-for="plugin in plugins"
          :key="plugin.plugin_id"
          class="plugin-card"
          @click="goDetail(plugin)"
        >
          <div class="card-header">
            <span class="icon">{{ plugin.icon || '🔌' }}</span>
            <div>
              <h3>{{ plugin.name }}</h3>
              <p class="author">{{ plugin.author }} · v{{ plugin.version }}</p>
            </div>
          </div>
          <p class="desc">{{ plugin.description }}</p>
          <div class="meta">
            <span>⭐ {{ plugin.rating_avg.toFixed(1) }}</span>
            <span>下载 {{ plugin.download_count }}</span>
            <el-tag v-if="plugin.is_official" size="small" type="success">官方</el-tag>
          </div>
          <el-button
            v-if="!plugin.is_installed"
            type="primary"
            size="small"
            class="install-btn"
            @click.stop="openInstall(plugin)"
          >
            安装
          </el-button>
          <el-tag v-else size="small" type="success">已安装</el-tag>
        </div>
      </div>
    </div>
    <p v-if="!loading && plugins.length === 0" class="empty">暂无插件</p>

    <InstallConfirmDialog
      v-if="pendingPlugin"
      v-model:visible="installDialogVisible"
      :plugin-name="pendingPlugin.name"
      :permissions="pendingPlugin.permissions"
      :loading="installing"
      @confirm="confirmInstall"
    />
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.search-input {
  width: 280px;
}
.layout {
  display: flex;
  gap: 24px;
}
.sidebar {
  width: 160px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cat-item {
  padding: 10px 12px;
  border: none;
  background: transparent;
  text-align: left;
  border-radius: 8px;
  cursor: pointer;
  color: #606266;
}
.cat-item.active,
.cat-item:hover {
  background: rgba(64, 158, 255, 0.08);
  color: #409eff;
}
.grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
.plugin-card {
  border: 1px solid #ebeef5;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: box-shadow 0.2s;
  position: relative;
}
.plugin-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.card-header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.icon {
  font-size: 28px;
}
.card-header h3 {
  margin: 0;
  font-size: 16px;
}
.author {
  margin: 4px 0 0;
  font-size: 12px;
  color: #909399;
}
.desc {
  font-size: 13px;
  color: #606266;
  margin: 12px 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.meta {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 12px;
  color: #909399;
}
.install-btn {
  margin-top: 12px;
}
.empty {
  text-align: center;
  color: #909399;
  padding: 40px;
}
</style>
