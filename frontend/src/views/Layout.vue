<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import AppHeader from '@/components/layout/AppHeader.vue';

const route = useRoute();

/** 聊天/工作流执行页使用全宽布局 */
const isFluidLayout = computed(() => {
  const fluidRoutes = ['AgentChat', 'KnowledgeChat', 'WorkflowExecute'];
  return fluidRoutes.includes(route.name as string);
});
</script>

<template>
  <div class="app-layout">
    <AppHeader />
    <main class="app-main">
      <div class="page-container" :class="{ 'page-container--fluid': isFluidLayout }">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<style lang="scss" scoped>
.app-layout {
  min-height: 100vh;
  background: $bg-white;
}

.app-main {
  padding: 24px 0 48px;
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
