import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const THEMES = {
  discord: {
    name: 'Discord',
    bg: '#ffffff', bgPanel: '#f8f9fa', bgDeep: '#f0f1f3', bgFloat: '#ffffff',
    text: '#1a1a2e', textSecondary: '#4a4a6a', textMuted: '#8888a8',
    border: 'rgba(0, 0, 0, 0.08)',
    accent: '#5865f2', accentHover: '#4752c4', accentLight: '#7289da',
    success: '#23a559', danger: '#f23f43', warning: '#f0b232', info: '#00a8fc',
  },
  dark: {
    name: 'Dark',
    bg: '#f5f6f8', bgPanel: '#ebedf0', bgDeep: '#e2e4e8', bgFloat: '#ffffff',
    text: '#1c1e21', textSecondary: '#606770', textMuted: '#8a8d91',
    border: 'rgba(0, 0, 0, 0.06)',
    accent: '#58a6ff', accentHover: '#4093e6', accentLight: '#79c0ff',
    success: '#3fb950', danger: '#f85149', warning: '#d29922', info: '#58a6ff',
  },
  midnight: {
    name: 'Midnight',
    bg: '#faf8ff', bgPanel: '#f3f0fa', bgDeep: '#ebe7f5', bgFloat: '#ffffff',
    text: '#2d1b69', textSecondary: '#6b5b95', textMuted: '#9b8fc2',
    border: 'rgba(0, 0, 0, 0.06)',
    accent: '#7c6aef', accentHover: '#6b59de', accentLight: '#9d8ff5',
    success: '#4caf7d', danger: '#ef5350', warning: '#ffb74d', info: '#7c6aef',
  },
}

export const useThemeStore = defineStore('theme', () => {
  const themeName = ref(localStorage.getItem('elaina_theme') || 'discord')
  const theme = computed(() => THEMES[themeName.value] || THEMES.discord)

  function setTheme(name) {
    themeName.value = name
    localStorage.setItem('elaina_theme', name)
    applyCSS(THEMES[name] || THEMES.discord)
  }

  function applyCSS(t) {
    const s = document.documentElement.style
    s.setProperty('--bg', t.bg)
    s.setProperty('--bg2', t.bgPanel)
    s.setProperty('--bg3', t.bgDeep)
    s.setProperty('--bg-float', t.bgFloat)
    s.setProperty('--text', t.text)
    s.setProperty('--text2', t.textSecondary)
    s.setProperty('--text3', t.textMuted)
    s.setProperty('--border', t.border)
    s.setProperty('--accent', t.accent)
    s.setProperty('--accent-hover', t.accentHover)
    s.setProperty('--accent-light', t.accentLight)
    s.setProperty('--success', t.success)
    s.setProperty('--danger', t.danger)
    s.setProperty('--warning', t.warning)
    s.setProperty('--info', t.info)
  }

  function naiveOverrides(t) {
    return {
      common: {
        primaryColor: t.accent, primaryColorHover: t.accentLight,
        primaryColorPressed: t.accentHover, primaryColorSuppl: t.accentLight,
        bodyColor: t.bg, baseColor: t.bgPanel, cardColor: t.bgPanel,
        modalColor: t.bgPanel, popoverColor: t.bgFloat,
        tableColor: t.bgPanel, tableColorHover: t.bgDeep,
        inputColor: t.bgDeep, inputColorDisabled: t.bgDeep,
        actionColor: t.bgPanel, tagColor: t.bgDeep,
        borderColor: t.border, dividerColor: t.border, hoverColor: t.bgDeep,
        textColorBase: t.text, textColor1: t.text,
        textColor2: t.textSecondary, textColor3: t.textMuted,
        placeholderColor: t.textMuted,
        successColor: t.success, errorColor: t.danger,
        warningColor: t.warning, infoColor: t.info,
        borderRadius: '12px', borderRadiusSmall: '8px',
      },
      Card: { colorEmbedded: t.bgDeep },
      DataTable: { thColor: t.bgDeep, tdColorHover: t.bgDeep },
      Menu: { itemTextColor: t.text, itemTextColorHover: t.accent, itemColorActive: t.bgDeep },
      Input: { color: t.bgDeep, colorFocus: t.bgFloat, textColor: t.text },
      Tag: { textColor: t.textSecondary },
    }
  }

  applyCSS(theme.value)

  return { themeName, theme, setTheme, applyCSS, naiveOverrides, THEMES }
})
