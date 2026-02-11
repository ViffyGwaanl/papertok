export type UiLang = 'zh' | 'en';

const STRINGS: Record<UiLang, Record<string, string>> = {
  zh: {
    // global
    about: '关于',
    likes: '喜欢',
    offlineModeTitle: '离线缓存模式：展示上次成功加载的内容',

    // about modal
    aboutTitle: '关于 PaperTok',
    aboutDesc: '一个 TikTok 风格的界面，用来浏览每日热门 AI/ML 论文。',
    author: '作者：Gwaanl',
    wechatOA: '公众号：书同文Suwin',
    github: 'GitHub：',

    // detail / markdown
    loadFailedPrefix: '加载失败：',
    cachedMayStale: '（离线缓存内容：可能不是最新）',
    noExplain: '（暂无讲解）',
    noMineruMd: '（没有 MinerU markdown）',
    loadingMarkdown: '加载 markdown…',
    loadFailed: '加载失败',

    // captions
    noCaption: '（暂无图注）',

    // share
    shareDialogTitle: '分享论文',
    linkCopied: '链接已复制',
  },
  en: {
    // global
    about: 'About',
    likes: 'Likes',
    offlineModeTitle: 'Offline cache mode: showing last successfully loaded content',

    // about modal
    aboutTitle: 'About PaperTok',
    aboutDesc: 'A TikTok-style interface for exploring daily trending AI/ML papers.',
    author: 'Author: Gwaanl',
    wechatOA: 'WeChat Official Account: 书同文Suwin',
    github: 'GitHub: ',

    // detail / markdown
    loadFailedPrefix: 'Load failed: ',
    cachedMayStale: '(Offline cached content: may be outdated)',
    noExplain: '(No explanation yet)',
    noMineruMd: '(No MinerU markdown)',
    loadingMarkdown: 'Loading markdown…',
    loadFailed: 'Load failed',

    // captions
    noCaption: '(No caption yet)',

    // share
    shareDialogTitle: 'Share paper',
    linkCopied: 'Link copied',
  },
};

export function t(lang: UiLang, key: string): string {
  const pack = STRINGS[lang] || STRINGS.zh;
  return pack[key] || STRINGS.zh[key] || key;
}
