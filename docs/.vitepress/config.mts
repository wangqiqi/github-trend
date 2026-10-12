import { defineConfig } from 'vitepress'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/**
 * 侧边栏由内容生成器产出（scripts/build_site_content.mjs）。
 *
 * 刻意只到「年 → 月」，不放逐日条目：SPIKE-001 实测 577 条逐日侧边栏会把
 * 产物从 50MB 撑到 173MB、单页 HTML 从 55KB 涨到 280KB（VitePress 会把
 * 主题配置序列化进每一页）。日期导航交给月度页与本地搜索。
 */
const sidebarFile = fileURLToPath(new URL('./sidebar.generated.json', import.meta.url))
const sidebar = existsSync(sidebarFile) ? JSON.parse(readFileSync(sidebarFile, 'utf-8')) : []

export default defineConfig({
  // 与 znza.top 的项目站点路径一致：https://znza.top/github-trend/
  base: '/github-trend/',
  lang: 'zh-CN',
  title: 'GitHub 热门榜单',
  description: '每日 GitHub 热门仓库榜单的归档与趋势（Star / Fork / 趋势榜 / Python）',
  cleanUrls: true,
  lastUpdated: false,

  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '每日榜单', link: '/daily/' },
      { text: '趋势', link: '/trends/' },
      { text: '数据说明', link: '/about' },
    ],
    sidebar,
    search: {
      provider: 'local',
      options: {
        translations: {
          button: { buttonText: '搜索', buttonAriaLabel: '搜索' },
          modal: {
            noResultsText: '没有找到结果',
            resetButtonTitle: '清除条件',
            footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
          },
        },
      },
    },
    outline: { level: [2, 3], label: '本页目录' },
    docFooter: { prev: '上一天', next: '下一天' },
    returnToTopLabel: '回到顶部',
    darkModeSwitchLabel: '主题',
    sidebarMenuLabel: '归档',
    footer: {
      message: '数据由 GitHub Actions 每日自动抓取 · 内容以仓库 data/ 为准',
      copyright: 'Powered by VitePress',
    },
  },
})
