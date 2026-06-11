import { createApp } from 'vue';
import { createI18n } from 'vue-i18n';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import * as ElementPlusIconsVue from '@element-plus/icons-vue';
import '@unocss/reset/tailwind.css';
import 'virtual:uno.css';

import App from './App.vue';
import { setupStore } from './stores';
import router from './router';
import '@/assets/styles/index.scss';
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';
import zhCN from '@/locales/zh-CN';
import enUS from '@/locales/en-US';

const SUPPORTED_LOCALES = ['zh-CN', 'en-US'] as const;
type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];
const DEFAULT_LOCALE: SupportedLocale = 'zh-CN';

function resolveInitialLocale(): SupportedLocale {
  const savedLocale = localStorage.getItem('locale') as SupportedLocale | null;
  if (savedLocale && SUPPORTED_LOCALES.includes(savedLocale)) {
    return savedLocale;
  }

  if (navigator.language.toLowerCase().startsWith('en')) {
    return 'en-US';
  }
  return DEFAULT_LOCALE;
}

(self as unknown as { MonacoEnvironment: { getWorker: () => Worker } }).MonacoEnvironment = {
  getWorker() {
    return new editorWorker();
  },
};

const i18n = createI18n({
  legacy: false,
  locale: resolveInitialLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
});

const app = createApp(App);

// 注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

setupStore(app);
app.use(router);
app.use(i18n);
app.use(ElementPlus);

app.mount('#app');
