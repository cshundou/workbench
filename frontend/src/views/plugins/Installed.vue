<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import PluginConfigDialog from '@/components/plugins/PluginConfigDialog.vue';
import {
  listInstalledPlugins,
  setPluginStatus,
  uninstallPlugin,
  updateInstalledPlugin,
  type PluginInfo,
} from '@/api/plugins';

const router = useRouter();
const loading = ref(false);
const plugins = ref<PluginInfo[]>([]);
const configVisible = ref(false);
const configPlugin = ref<PluginInfo | null>(null);

async function fetchData(): Promise<void> {
  loading.value = true;
  try {
    plugins.value = await listInstalledPlugins();
  } finally {
    loading.value = false;
  }
}

async function toggleStatus(plugin: PluginInfo): Promise<void> {
  const enabled = plugin.installation?.status !== 'enabled';
  await setPluginStatus(plugin.plugin_id, enabled);
  ElMessage.success(enabled ? '已启用' : '已禁用');
  fetchData();
}

function openConfig(plugin: PluginInfo): void {
  configPlugin.value = plugin;
  configVisible.value = true;
}

async function handleUpdate(plugin: PluginInfo): Promise<void> {
  await updateInstalledPlugin(plugin.plugin_id);
  ElMessage.success('插件已更新');
  fetchData();
}

async function handleUninstall(plugin: PluginInfo): Promise<void> {
  await ElMessageBox.confirm(`确定卸载 ${plugin.name}？`, '确认卸载', { type: 'warning' });
  await uninstallPlugin(plugin.plugin_id);
  ElMessage.success('已卸载');
  fetchData();
}

onMounted(fetchData);
</script>

<template>
  <div>
    <SectionHeader title="已安装插件" description="管理租户已安装的插件">
      <template #actions>
        <el-button @click="router.push({ name: 'PluginMarketplace' })">插件市场</el-button>
      </template>
    </SectionHeader>
    <div v-loading="loading" class="list">
      <el-card v-for="plugin in plugins" :key="plugin.plugin_id" class="item">
        <div class="row">
          <span class="icon">{{ plugin.icon || '🔌' }}</span>
          <div class="info">
            <h3>
              <span
                class="status-dot"
                :class="plugin.installation?.status === 'enabled' ? 'on' : 'off'"
              />
              {{ plugin.name }}
              <el-tag v-if="plugin.installation?.has_update" size="small" type="warning">
                有更新
              </el-tag>
            </h3>
            <p class="desc">{{ plugin.description }}</p>
            <p class="meta">版本 v{{ plugin.installation?.installed_version }}</p>
          </div>
          <div class="actions">
            <el-button size="small" @click="openConfig(plugin)">配置</el-button>
            <el-button
              v-if="plugin.installation?.has_update"
              size="small"
              type="warning"
              @click="handleUpdate(plugin)"
            >
              更新
            </el-button>
            <el-button
              size="small"
              @click="toggleStatus(plugin)"
            >
              {{ plugin.installation?.status === 'enabled' ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" @click="handleUninstall(plugin)">
              卸载
            </el-button>
          </div>
        </div>
      </el-card>
      <p v-if="!loading && plugins.length === 0" class="empty">暂无已安装插件</p>
    </div>

    <PluginConfigDialog
      v-if="configPlugin"
      v-model:visible="configVisible"
      :plugin-id="configPlugin.plugin_id"
      :plugin-name="configPlugin.name"
      :initial-config="(configPlugin.installation?.config as Record<string, unknown>) || {}"
      @saved="fetchData"
    />
  </div>
</template>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.item {
  margin-bottom: 0;
}
.row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.icon {
  font-size: 32px;
}
.info {
  flex: 1;
}
.info h3 {
  margin: 0 0 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.status-dot.on {
  background: #67c23a;
}
.status-dot.off {
  background: #f56c6c;
}
.desc {
  margin: 0;
  color: #606266;
  font-size: 14px;
}
.meta {
  margin: 8px 0 0;
  font-size: 12px;
  color: #909399;
}
.actions {
  display: flex;
  gap: 8px;
}
.empty {
  text-align: center;
  color: #909399;
  padding: 40px;
}
</style>
