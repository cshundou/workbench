import {
  defineConfig,
  presetAttributify,
  presetIcons,
  presetUno,
  transformerDirectives,
  transformerVariantGroup,
} from 'unocss';

export default defineConfig({
  presets: [
    presetUno(),
    presetAttributify(),
    presetIcons({
      scale: 1.2,
      warn: true,
    }),
  ],
  transformers: [transformerDirectives(), transformerVariantGroup()],
  shortcuts: {
    'flex-center': 'flex items-center justify-center',
    'flex-between': 'flex items-center justify-between',
    'page-container': 'w-full max-w-1200px mx-auto px-10',
    'section-block': 'mb-16',
  },
  theme: {
    colors: {
      primary: '#FF5A1F',
      'primary-start': '#FF5C4D',
      'primary-end': '#FF8A65',
      success: '#00B42A',
      warning: '#FF7D00',
      danger: '#F53F3F',
      info: '#86909C',
    },
    borderRadius: {
      sm: '8px',
      md: '12px',
      lg: '16px',
      pill: '999px',
    },
    boxShadow: {
      card: '0 4px 24px rgba(0, 0, 0, 0.06)',
      'card-hover': '0 8px 32px rgba(0, 0, 0, 0.1)',
    },
  },
});
