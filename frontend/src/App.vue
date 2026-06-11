<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { ElConfigProvider } from 'element-plus';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import en from 'element-plus/es/locale/lang/en';

const { locale } = useI18n();

const elementLocale = computed(() => (locale.value === 'en-US' ? en : zhCn));
</script>

<template>
  <ElConfigProvider :locale="elementLocale">
    <router-view />
  </ElConfigProvider>
</template>

<style lang="scss">
html,
body,
#app {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
}
</style>
