import { createApp } from 'vue';
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

(self as unknown as { MonacoEnvironment: { getWorker: () => Worker } }).MonacoEnvironment = {
  getWorker() {
    return new editorWorker();
  },
};

const app = createApp(App);

// 注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

setupStore(app);
app.use(router);
app.use(ElementPlus);

app.mount('#app');
