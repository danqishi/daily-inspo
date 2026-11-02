# 每日灵感

每天北京时间 7 点左右自动生成一份灵感日报，8 点前就能在网站上看到。

| 栏目 | 频率 |
|---|---|
| 🤖 AI 创意视频 / AI 剧情片 | 每天 1 条 |
| ✨ 创意视频（财经、访谈类每月最多 10 次） | 每天 1 条 |
| 🛠 AI 视频和图片制作资讯 | 周一到周五每天 2 条 |
| 🔥 抖音热梗 | 周一到周五每天 1 条 |
| 🎵 抖音热门音乐 | 周一到周五每天 2 首 |
| 🎨 设计风格（带例图） | 每天 1 种 |
| 🎼 音乐风格 + 代表曲 + 乐器 | 每天 1 组 |
| 🖼 画作 / 摄影赏析（交替） | 每天 1 幅 |

## 第一次设置

1. 在 GitHub 新建一个**公开**仓库，把这个文件夹的内容推上去。
2. 仓库 → Settings → Secrets and variables → Actions → **New repository secret**，添加两个：
   - `ZHIPU_API_KEY`：智谱开放平台 https://open.bigmodel.cn 的 API Key
   - `TAVILY_API_KEY`：Tavily https://tavily.com 的 API Key
3. 仓库 → Settings → Pages → Source 选 **Deploy from a branch**，分支选 `main`，文件夹选 `/docs`，保存。
4. 仓库 → Actions → 「每日灵感」→ **Run workflow**，手动跑第一次（大约 5–10 分钟）。
5. 打开 `https://你的用户名.github.io/仓库名/`。手机上用浏览器的“添加到主屏幕”，用起来就像一个 App。

## 常用操作

- **某个栏目今天没生成 / 想重新生成**：Actions → Run workflow，`only` 填栏目名（如 `meme,artwork`）。
  栏目名：`ai_video` `creative_video` `ai_news` `meme` `hot_music` `design_style` `music_style` `artwork`
- **整天重新生成**：Run workflow，勾选 `force`。
- **换成付费 AI**（质量更好）：Settings → Secrets and variables → Actions → **Variables** 里添加 `LLM_PROVIDER`：
  - `deepseek`：再加一个 Secret `DEEPSEEK_API_KEY`（每月约 10–30 元）
  - `claude`：再加一个 Secret `ANTHROPIC_API_KEY`
- **看运行记录**：Actions 页面，红色叉号表示那天失败了，点进去能看到原因。

## 本地预览（可选）

```
pip install -r requirements.txt
python generator/main.py --dry-run --site preview   # 先把 docs 复制一份到 preview
cd preview && python -m http.server 8765            # 浏览器打开 http://localhost:8765
```

## 说明

- AI 看不了视频，视频解读是根据标题、简介和网上的评价整理的。
- 抖音、小红书没有公开接口，推荐的视频以 B 站、YouTube 为主。
- 画作和摄影来自大都会博物馆的公有领域馆藏；设计风格的例图来自网络和维基共享资源，只用于个人学习。
- 已读标记只保存在当前设备的浏览器里。
