import type { App } from 'vue';
import { createPinia } from 'pinia';

const pinia = createPinia();

/** 安装 Pinia 到 Vue 应用 */
export function setupStore(app: App): void {
  app.use(pinia);
}

export { pinia };
export * from './user';
export * from './rag';
export * from './graph';
