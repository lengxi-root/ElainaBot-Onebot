/**
 * 从原始 dist CSS 提取样式 → 写入 Vue 源码的 <style scoped>
 * 用法: node sync-css.js
 */
const fs = require('fs')
const path = require('path')

const DIST_CSS = path.resolve(__dirname, '../ElainaBot_v2/web/dist/assets')
const SRC_VIEWS = path.resolve(__dirname, 'src/views')
const SRC_COMP = path.resolve(__dirname, 'src/components')

// CSS 文件 → Vue 文件映射
const MAP = {
  'Layout.css': `${SRC_VIEWS}/Layout.vue`,
  'Login.css': `${SRC_VIEWS}/Login.vue`,
  'Config.css': `${SRC_VIEWS}/Config.vue`,
  'Dashboard.css': `${SRC_VIEWS}/Dashboard.vue`,
  'Database.css': `${SRC_VIEWS}/Database.vue`,
  'Logs.css': `${SRC_VIEWS}/Logs.vue`,
  'Market.css': `${SRC_VIEWS}/Market.vue`,
  'Messages.css': `${SRC_VIEWS}/Messages.vue`,
  'OpenAPI.css': `${SRC_VIEWS}/OpenAPI.vue`,
  'Plugins.css': `${SRC_VIEWS}/Plugins.vue`,
  'Statistics.css': `${SRC_VIEWS}/Statistics.vue`,
  'CustomPage.css': `${SRC_VIEWS}/CustomPage.vue`,
  'SvgIcon.css': `${SRC_COMP}/SvgIcon.vue`,
}

function unminify(css) {
  // 去掉 scoped hash [data-v-xxxxxxxx]
  css = css.replace(/\[data-v-[a-f0-9]+\]/g, '')
  // 格式化
  css = css
    .replace(/\{/g, ' {\n  ')
    .replace(/;/g, ';\n  ')
    .replace(/\}/g, '\n}\n')
    .replace(/\n  \n/g, '\n')
    .replace(/\n\n+/g, '\n')
    .trim()
  return css
}

function replaceStyle(vuePath, newCss) {
  let content = fs.readFileSync(vuePath, 'utf-8')
  // 替换 <style scoped>...</style>
  const styleRe = /<style\s+scoped>[\s\S]*?<\/style>/
  const newStyle = `<style scoped>\n${newCss}\n</style>`
  if (styleRe.test(content)) {
    content = content.replace(styleRe, newStyle)
  } else {
    // 追加
    content = content.trimEnd() + '\n\n' + newStyle + '\n'
  }
  fs.writeFileSync(vuePath, content, 'utf-8')
}

let count = 0
for (const [cssFile, vuePath] of Object.entries(MAP)) {
  const cssPath = path.join(DIST_CSS, cssFile)
  if (!fs.existsSync(cssPath) || !fs.existsSync(vuePath)) {
    console.log(`⚠ 跳过: ${cssFile} (文件不存在)`)
    continue
  }
  const raw = fs.readFileSync(cssPath, 'utf-8')
  const formatted = unminify(raw)
  replaceStyle(vuePath, formatted)
  console.log(`✓ ${cssFile} → ${path.basename(vuePath)}`)
  count++
}
console.log(`\n完成: ${count} 个组件样式已同步`)
