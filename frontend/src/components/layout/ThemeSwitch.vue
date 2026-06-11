<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Moon, Sunny } from '@element-plus/icons-vue';

const isDark = ref(false);

function applyTheme(dark: boolean): void {
  isDark.value = dark;
  document.documentElement.classList.toggle('dark', dark);
  localStorage.setItem('theme', dark ? 'dark' : 'light');
}

function toggleTheme(): void {
  applyTheme(!isDark.value);
}

onMounted(() => {
  applyTheme(localStorage.getItem('theme') === 'dark');
});
</script>

<template>
  <el-button circle :icon="isDark ? Sunny : Moon" @click="toggleTheme" />
</template>
