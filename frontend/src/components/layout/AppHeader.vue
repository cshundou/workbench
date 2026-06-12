<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import { ElMessageBox } from 'element-plus';
import {
  Odometer,
  Collection,
  Cpu,
  Share,
  DataAnalysis,
  Connection,
  Setting,
  User,
  Key,
  Menu,
} from '@element-plus/icons-vue';
import type { Component } from 'vue';
import { useUserStore } from '@/stores/user';
import { useAppConfigStore } from '@/stores/appConfig';
import { ROUTE_PERMISSIONS } from '@/constants/permissions';
import AppLogo from '@/components/layout/AppLogo.vue';
import ThemeSwitch from '@/components/layout/ThemeSwitch.vue';

interface NavItem {
  path: string;
  titleKey: string;
  icon?: Component;
  permission: string | null;
}

type SupportedLocale = 'zh-CN' | 'en-US';

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const appConfig = useAppConfigStore();
const { t, locale } = useI18n();

const mobileMenuVisible = ref(false);

/** 顶部主导航项 */
const topMenuItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [
    { path: '/dashboard', titleKey: 'nav.dashboard', icon: Odometer, permission: null },
    {
      path: '/knowledge',
      titleKey: 'nav.knowledge',
      icon: Collection,
      permission: ROUTE_PERMISSIONS.knowledge,
    },
    {
      path: '/agents',
      titleKey: 'nav.agents',
      icon: Cpu,
      permission: ROUTE_PERMISSIONS.agents,
    },
    {
      path: '/workflows',
      titleKey: 'nav.workflows',
      icon: Share,
      permission: ROUTE_PERMISSIONS.workflows,
    },
    {
      path: '/monitor',
      titleKey: 'nav.monitor',
      icon: DataAnalysis,
      permission: ROUTE_PERMISSIONS.monitor,
    },
    {
      path: '/plugins/marketplace',
      titleKey: 'nav.plugins',
      icon: Connection,
      permission: ROUTE_PERMISSIONS.agents,
    },
  ];

  if (!userStore.isLoggedIn && appConfig.authMode === 'optional') {
    return items;
  }
  return items.filter((item) => !item.permission || userStore.hasPermission(item.permission));
});

/** 设置子菜单项 */
const settingsMenuItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [
    {
      path: '/settings/api-keys',
      titleKey: 'nav.apiKeys',
      icon: Key,
      permission: null,
    },
    {
      path: '/settings/users',
      titleKey: 'nav.users',
      icon: User,
      permission: ROUTE_PERMISSIONS.userManagement,
    },
    {
      path: '/settings/roles',
      titleKey: 'nav.roles',
      icon: Key,
      permission: ROUTE_PERMISSIONS.roleManagement,
    },
  ];

  return items.filter((item) => !item.permission || userStore.hasPermission(item.permission));
});

const languageOptions = computed(() => [
  { value: 'zh-CN' as SupportedLocale, label: t('header.languageZhCN') },
  { value: 'en-US' as SupportedLocale, label: t('header.languageEnUS') },
]);

const currentLanguage = computed<SupportedLocale>({
  get: () => (locale.value === 'en-US' ? 'en-US' : 'zh-CN'),
  set: (value) => {
    locale.value = value;
    localStorage.setItem('locale', value);
  },
});

const displayName = computed(() => userStore.userInfo?.username || t('header.defaultUser'));

const isSettingsActive = computed(() => route.path.startsWith('/settings'));

/** 判断导航项是否激活 */
function isNavActive(path: string): boolean {
  if (path === '/dashboard') {
    return route.path === '/dashboard';
  }
  return route.path.startsWith(path);
}

function handleNavClick(path: string): void {
  mobileMenuVisible.value = false;
  router.push(path);
}

async function handleLogout(): Promise<void> {
  try {
    await ElMessageBox.confirm(t('header.logoutConfirmMessage'), t('header.logoutConfirmTitle'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
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
  <header class="app-header">
    <div class="header-inner flex-between">
      <!-- Logo -->
      <div class="header-logo" @click="handleNavClick('/dashboard')">
        <AppLogo />
      </div>

      <!-- 桌面导航 -->
      <nav class="header-nav desktop-nav">
        <button
          v-for="item in topMenuItems"
          :key="item.path"
          class="nav-item"
          :class="{ 'is-active': isNavActive(item.path) }"
          @click="handleNavClick(item.path)"
        >
          {{ t(item.titleKey) }}
        </button>

        <el-dropdown v-if="settingsMenuItems.length > 0" trigger="click">
          <button class="nav-item" :class="{ 'is-active': isSettingsActive }">
            <el-icon class="nav-icon"><Setting /></el-icon>
            {{ t('nav.settings') }}
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="item in settingsMenuItems"
                :key="item.path"
                @click="handleNavClick(item.path)"
              >
                <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
                {{ t(item.titleKey) }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </nav>

      <!-- 右侧用户区 -->
      <div class="header-right flex-center">
        <el-select v-model="currentLanguage" size="small" class="language-switch">
          <el-option
            v-for="option in languageOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <ThemeSwitch class="theme-switch" />
        <el-button
          v-if="!userStore.isLoggedIn"
          type="primary"
          round
          @click="router.push({ name: 'Login', query: { redirect: route.fullPath } })"
        >
          {{ t('header.login') }}
        </el-button>
        <el-dropdown v-else trigger="click">
          <span class="user-dropdown flex-center">
            <el-avatar :size="32" class="user-avatar">
              {{ displayName.charAt(0).toUpperCase() }}
            </el-avatar>
            <span class="user-name">{{ displayName }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleLogout">{{ t('header.logout') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <!-- 移动端汉堡按钮 -->
        <el-button class="mobile-menu-btn" text @click="mobileMenuVisible = true">
          <el-icon :size="22"><Menu /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 移动端抽屉菜单 -->
    <el-drawer
      v-model="mobileMenuVisible"
      direction="rtl"
      size="280px"
      :title="t('nav.drawerTitle')"
      :with-header="true"
    >
      <div class="mobile-nav">
        <button
          v-for="item in topMenuItems"
          :key="item.path"
          class="mobile-nav-item"
          :class="{ 'is-active': isNavActive(item.path) }"
          @click="handleNavClick(item.path)"
        >
          <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
          {{ t(item.titleKey) }}
        </button>

        <div v-if="settingsMenuItems.length > 0" class="mobile-nav-group">
          <p class="mobile-nav-label">{{ t('nav.settingsGroup') }}</p>
          <button
            v-for="item in settingsMenuItems"
            :key="item.path"
            class="mobile-nav-item"
            :class="{ 'is-active': route.path === item.path }"
            @click="handleNavClick(item.path)"
          >
            <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
            {{ t(item.titleKey) }}
          </button>
        </div>
      </div>
    </el-drawer>
  </header>
</template>

<style lang="scss" scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 100;
  height: $header-height;
  background: rgba($bg-white, 0.92);
  backdrop-filter: blur(12px);
  box-shadow: $shadow-soft;
}

.header-inner {
  height: 100%;
  max-width: $content-max-width;
  margin: 0 auto;
  padding: 0 $content-padding;
}

.header-logo {
  cursor: pointer;
  flex-shrink: 0;
}

.header-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  justify-content: center;
  margin: 0 24px;

  @media (max-width: 1024px) {
    display: none;
  }
}

.nav-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border: none;
  background: transparent;
  color: $text-regular;
  font-size: 14px;
  cursor: pointer;
  border-radius: $border-radius-pill;
  transition: all 0.2s ease;
  white-space: nowrap;

  &:hover {
    color: $text-primary;
    background: rgba($primary-color, 0.06);
  }

  &.is-active {
    color: $primary-color;
    font-weight: 600;
    background: rgba($primary-color, 0.08);
  }
}

.nav-icon {
  font-size: 14px;
}

.header-right {
  gap: 8px;
  flex-shrink: 0;
}

.language-switch {
  width: 120px;

  @media (max-width: 768px) {
    width: 104px;
  }
}

.user-dropdown {
  cursor: pointer;
  gap: 8px;
}

.user-avatar {
  background: $primary-color;
  color: #fff;
}

.user-name {
  color: $text-primary;
  font-size: 14px;

  @media (max-width: 768px) {
    display: none;
  }
}

.mobile-menu-btn {
  display: none;
  color: $text-primary;

  @media (max-width: 1024px) {
    display: inline-flex;
  }
}

.mobile-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mobile-nav-group {
  margin-top: 16px;
  padding-top: 16px;
}

.mobile-nav-label {
  margin: 0 0 8px;
  padding: 0 12px;
  font-size: 12px;
  color: $text-secondary;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mobile-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 12px 16px;
  border: none;
  background: transparent;
  color: $text-regular;
  font-size: 15px;
  cursor: pointer;
  border-radius: $border-radius-md;
  text-align: left;
  transition: all 0.2s ease;

  &:hover {
    background: rgba($primary-color, 0.06);
    color: $text-primary;
  }

  &.is-active {
    background: rgba($primary-color, 0.08);
    color: $primary-color;
    font-weight: 600;
  }
}
</style>
