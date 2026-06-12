#!/usr/bin/env node
/**
 * Agent Platform 插件脚手架 CLI。
 * Usage: agent-plugin create <name>
 */
const fs = require('fs');
const path = require('path');

const cmd = process.argv[2];
const name = process.argv[3];

if (cmd !== 'create' || !name) {
  console.log('Usage: agent-plugin create <plugin-name>');
  process.exit(1);
}

const pluginId = name.toLowerCase().replace(/\s+/g, '-');
const dir = path.join(process.cwd(), pluginId);

const manifest = {
  plugin_id: pluginId,
  name: name,
  description: `${name} plugin`,
  author: 'Developer',
  version: '1.0.0',
  category: 'dev',
  permissions: ['network:outbound'],
  skills: ['main-skill'],
};

const skillTs = `import { defineSkill, permissions } from '@agent-platform/sdk';

export default defineSkill({
  name: 'main-skill',
  description: 'Main skill for ${name}',
  permissions: [permissions.NETWORK_OUTBOUND],
  parameters: {
    type: 'object',
    properties: { input: { type: 'string' } },
    required: ['input'],
  },
  async execute({ input }) {
    return { echo: input };
  },
});
`;

fs.mkdirSync(path.join(dir, 'skills'), { recursive: true });
fs.writeFileSync(path.join(dir, 'manifest.json'), JSON.stringify(manifest, null, 2));
fs.writeFileSync(path.join(dir, 'skills', 'main-skill.ts'), skillTs);
fs.writeFileSync(
  path.join(dir, 'package.json'),
  JSON.stringify({ name: pluginId, version: '1.0.0', private: true }, null, 2),
);

console.log(`Created plugin at ${dir}`);
console.log('Next: cd', pluginId, '&& npm install @agent-platform/sdk');
