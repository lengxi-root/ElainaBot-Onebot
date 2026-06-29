import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const THEMES = {
  discord: {
    name: '清新蓝',
    bg: '#f4f6fb', bgPanel: '#ffffff', bgDeep: '#f1f4f9', bgFloat: '#ffffff',
    text: '#1f2733', textSecondary: '#5b6675', textMuted: '#97a1b0',
    border: '#eef1f6',
    accent: '#3b7bf7', accentHover: '#2f6ae0', accentLight: '#6fa0fb',
    accentSoft: 'rgba(59, 123, 247, 0.1)',
    success: '#22c55e', danger: '#ef4444', warning: '#f59e0b', info: '#3b7bf7',
  },
  dark: {
    name: '石墨灰',
    bg: '#f5f6f8', bgPanel: '#ffffff', bgDeep: '#eef0f3', bgFloat: '#ffffff',
    text: '#1c2128', textSecondary: '#57606a', textMuted: '#8a93a0',
    border: '#eceef1',
    accent: '#2f6feb', accentHover: '#1f5fd8', accentLight: '#6398f5',
    accentSoft: 'rgba(47, 111, 235, 0.1)',
    success: '#2ea043', danger: '#e5484d', warning: '#d29922', info: '#2f6feb',
  },
  midnight: {
    name: '梦幻紫',
    bg: '#f8f6fe', bgPanel: '#ffffff', bgDeep: '#f3effb', bgFloat: '#ffffff',
    text: '#2a2150', textSecondary: '#6b5f93', textMuted: '#a094c0',
    border: '#efeafa',
    accent: '#7c5cf6', accentHover: '#6a49ee', accentLight: '#a48ff9',
    accentSoft: 'rgba(124, 92, 246, 0.1)',
    success: '#22c55e', danger: '#ef4444', warning: '#f59e0b', info: '#7c5cf6',
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
    s.setProperty('--accent-soft', t.accentSoft)
    s.setProperty('--success', t.success)
    s.setProperty('--danger', t.danger)
    s.setProperty('--warning', t.warning)
    s.setProperty('--info', t.info)
    s.setProperty('--radius', '16px')
    s.setProperty('--radius-sm', '10px')
    s.setProperty('--shadow', '0 1px 2px rgba(16,24,40,.04), 0 4px 12px rgba(16,24,40,.05)')
    s.setProperty('--shadow-sm', '0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06)')
    s.setProperty('--shadow-hover', '0 4px 10px rgba(16,24,40,.06), 0 10px 24px rgba(16,24,40,.08)')
  }

  function naiveOverrides(t) {
    return {
      common: {
        primaryColor: t.accent, primaryColorHover: t.accentLight,
        primaryColorPressed: t.accentHover, primaryColorSuppl: t.accentLight,
        bodyColor: t.bg, baseColor: t.bgPanel, cardColor: t.bgPanel,
        modalColor: t.bgPanel, popoverColor: t.bgFloat,
        tableColor: t.bgPanel, tableColorHover: t.bgDeep,
        inputColor: t.bgPanel, inputColorDisabled: t.bgDeep,
        actionColor: t.bgDeep, tagColor: t.bgDeep,
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
      Input: { color: t.bgPanel, colorFocus: t.bgFloat, textColor: t.text },
      Tag: { textColor: t.textSecondary },
    }
  }

  applyCSS(theme.value)

  return { themeName, theme, setTheme, applyCSS, naiveOverrides, THEMES }
})
