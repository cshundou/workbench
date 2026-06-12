# Agent Platform Plugin SDK

TypeScript/JavaScript SDK for building platform plugins and Skills.

## Quick Start

```bash
npm install @agent-platform/sdk
npx agent-plugin create my-plugin
cd my-plugin
npm run dev
npm run build
```

## Backend Skill Handler

```typescript
import { defineSkill, storage, permissions } from '@agent-platform/sdk';

export default defineSkill({
  name: 'send-message',
  description: 'Send a message via integration',
  permissions: [permissions.NETWORK_OUTBOUND],
  parameters: {
    type: 'object',
    properties: {
      to: { type: 'string' },
      text: { type: 'string' },
    },
    required: ['to', 'text'],
  },
  async execute({ to, text }) {
    await storage.set('last_recipient', to);
    return { sent: true, to, text };
  },
});
```

## Frontend Page Extension

```typescript
import { definePage } from '@agent-platform/sdk/frontend';

export default definePage({
  route: '/plugins/my-plugin/settings',
  component: () => import('./Settings.vue'),
});
```

## API Reference

See `docs/` in this package for full API documentation.
