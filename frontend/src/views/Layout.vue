<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessageBox } from 'element-plus';
import {
  Odometer,
  Collection,
  Cpu,
  Share,
  DataAnalysis,
  Setting,
  Fold,
  Expand,
  User,
  Key,
} from '@element-plus/icons-vue';
import { useUserStore } from '@/stores/user';
import { ROUTE_PERMISSIONS } from '@/constants/permissions';

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

const isCollapsed = ref(false);

/** 顶部级菜单项（不含设置子菜单） */
const topMenuItems = computed(() => {
  const items = [
    { path: '/dashboard', title: '控制台', icon: Odometer, permission: null },
    {
      path: '/knowledge',
      title: '知识库',
      icon: Collection,
      permission: ROUTE_PERMISSIONS.knowledge,
    },
    {
      path: '/agents',
      title: '智能体',
      icon: Cpu,
      permission: ROUTE_PERMISSIONS.agents,
    },
    {
      path: '/workflows',
      title: '工作流',
      icon: Share,
      permission: ROUTE_PERMISSIONS.workflows,
    },
    {
      path: '/monitor',
      title: '监控面板',
      icon: DataAnalysis,
      permission: ROUTE_PERMISSIONS.monitor,
    },
  ];

  return items.filter(
    (item) => !item.permission || userStore.hasPermission(item.permission),
  );
});

/** 设置子菜单项（API 密钥管理对所有登录用户可见） */
const settingsMenuItems = computed(() => {
  const items = [
    {
      path: '/settings/api-keys',
      title: 'API 密钥管理',
      icon: Key,
      permission: null,
    },
    {
      path: '/settings/users',
      title: '用户管理',
      icon: User,
      permission: ROUTE_PERMISSIONS.userManagement,
    },
    {
      path: '/settings/roles',
      title: '角色管理',
      icon: Key,
      permission: ROUTE_PERMISSIONS.roleManagement,
    },
  ];

  return items.filter(
    (item) => !item.permission || userStore.hasPermission(item.permission),
  );
});

/** 是否显示设置子菜单 */
const showSettingsMenu = computed(
  () => settingsMenuItems.value.length > 0 || userStore.isLoggedIn,
);

const activeMenu = computed(() => route.path);
const pageTitle = computed(() => (route.meta.title as string) || '企业智能协作工作台');
const displayName = computed(() => userStore.userInfo?.username || '用户');

function toggleSidebar(): void {
  isCollapsed.value = !isCollapsed.value;
}

function handleMenuSelect(path: string): void {
  router.push(path);
}

async function handleLogout(): Promise<void> {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    });
    userStore.logout();
    router.push({ name: 'Login' });
  } catch {
    // 用户取消
  }
}
</script>

<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapsed ? '64px' : '240px'" class="layout-aside">
      <div class="logo-area flex-center">
        <span v-if="!isCollapsed" class="logo-text">企业智能协作工作台</span>
        <span v-else class="logo-text-mini">AI</span>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        :collapse-transition="false"
        class="sidebar-menu"
        @select="handleMenuSelect"
      >
        <el-menu-item
          v-for="item in topMenuItems"
          :key="item.path"
          :index="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>

        <el-sub-menu v-if="showSettingsMenu" index="settings">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </template>
          <el-menu-item
            v-for="item in settingsMenuItems"
            :key="item.path"
            :index="item.path"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <template #title>{{ item.title }}</template>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <el-container class="layout-main">
      <!-- 顶部导航 -->
      <el-header class="layout-header flex-between">
        <div class="header-left flex-center">
          <el-button text class="collapse-btn" @click="toggleSidebar">
            <el-icon :size="20">
              <Fold v-if="!isCollapsed" />
              <Expand v-else />
            </el-icon>
          </el-button>
          <span class="page-title">{{ pageTitle }}</span>
        </div>

        <div class="header-right flex-center">
          <el-dropdown trigger="click">
            <span class="user-dropdown flex-center">
              <el-avatar :size="32" class="user-avatar">
                {{ displayName.charAt(0).toUpperCase() }}
              </el-avatar>
              <span class="user-name">{{ displayName }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="layout-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style lang="scss" scoped>
.layout-container {
  width: 100%;
  height: 100vh;
  background: $bg-white;
}

.layout-aside {
  background-color: $bg-color;
  border-right: 1px solid $border-color;
  transition: width 0.2s ease;
  overflow: hidden;
}

.logo-area {
  height: $header-height;
  color: $text-primary;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid $border-color;
  padding: 0 16px;
}

.logo-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.logo-text-mini {
  font-size: 16px;
  color: $primary-color;
  font-weight: 700;
}

.sidebar-menu {
  --el-menu-bg-color: #{$bg-color};
  --el-menu-text-color: #{$text-regular};
  --el-menu-active-color: #{$primary-color};
  --el-menu-hover-bg-color: #{rgba($primary-color, 0.06)};
  --el-menu-hover-text-color: #{$text-primary};
  border-right: none;
  padding: 8px 0;

  :deep(.el-menu-item.is-active) {
    background-color: rgba($primary-color, 0.08);
    font-weight: 600;
  }

  :deep(.el-sub-menu__title:hover),
  :deep(.el-menu-item:hover) {
    background-color: rgba($primary-color, 0.06);
  }
}

.layout-main {
  background-color: $bg-white;
}

.layout-header {
  height: $header-height;
  background-color: $bg-white;
  border-bottom: 1px solid $border-color;
  padding: 0 $content-padding;
}

.collapse-btn {
  margin-right: 12px;
  color: $text-primary;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.user-dropdown {
  cursor: pointer;
  gap: 8px;
}

.user-avatar {
  background-color: $primary-color;
  color: #fff;
  border-radius: $border-radius;
}

.user-name {
  color: $text-primary;
  font-size: 14px;
}

.layout-content {
  padding: 24px $content-padding;
  overflow-y: auto;
  background: $bg-white;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
