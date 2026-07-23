# 英语词汇学习主页

返回：学习索引 · 搜索：英语词汇检索索引 · 复习方法：[词汇复习与应用](vocabulary-review.html) · 数据视图：英语词汇数据库

> [!summary] 这不是一份需要从头背到尾的词表
> 这里把阅读、课程、视频和生活中真正遇到的词，整理成可查、可复习、可输出的 canonical cards。一个原形或固定短语只保留一张卡，复数、过去式、`-ing` 等形式写入 `aliases` 和 `forms`。

## 入口

- **记录新词**：在 Obsidian 中按 `Ctrl+P`，运行 `QuickAdd: 记录英语生词`。新批次会保存到 `00_Inbox/YYYY-MM-DD-HHmm-标题.md`。
- **整理新词**：使用 英语词汇整理提示词，先恢复原形、查重，再创建或更新词卡。
- **开始复习**：先看下方“今日到期”，闭卷回忆后再打开卡片核对。
- **需要完整说明**：查看 第一次使用教程。

## 先搜索，不要逐个点文件

1. **一页内搜索**：打开 英语词汇检索索引，按 `Ctrl+F`；英文原形、遇见形式和中文核心义都能命中。
2. **按名称直达**：在 Obsidian 按 `Ctrl+O`，输入 lemma、复数、过去式或 aliases，直接打开 canonical card。
3. **搜正文与例句**：按 `Ctrl+Shift+F`，输入词或中文义，再把搜索路径限定为 `学习/英语词汇`。
4. **表格筛选**：打开 英语词汇数据库，使用“词汇检索”“今日复习”“优先复习”“重复遇见”“反复遗忘”“固定短语”“真题来源”或“来源待核”视图。

成功信号：无需知道文件名，只要记得英文变体、中文义或例句片段，就能定位到唯一词卡。

## 优先复习

> [!note] 交互式数据库请在私有 Obsidian Vault 中查看；公开页使用下方静态词卡索引。
## 今日到期

> [!note] 交互式数据库请在私有 Obsidian Vault 中查看；公开页使用下方静态词卡索引。
## 重复遇见与遗忘

同一词再次出现时更新原卡，不新建第二个文件。普通再遇见会提高 `encounter_count`；明确“又忘了”时同时提高 `lapse_count`，并把复习拉回今天或次日。

> [!note] 交互式数据库请在私有 Obsidian Vault 中查看；公开页使用下方静态词卡索引。
如果要直接记录一次学习事件，在 **Windows PowerShell** 的 Vault 根目录运行：

```powershell
# 再次遇见，但仍记得
python _System\Scripts\vocabulary-progress.py --term "testimony" --event encounter --observed-form testimonies

# 再次遇见，而且忘了
python _System\Scripts\vocabulary-progress.py --term "bear" --event lapse --observed-form bore

# 完成一次复习
python _System\Scripts\vocabulary-progress.py --term "bear" --event review --result good
```

成功信号：命令输出修改前后计数、优先级和下次复习日，同时自动刷新“英语词汇检索索引”。

## 来源待核

> [!note] 交互式数据库请在私有 Obsidian Vault 中查看；公开页使用下方静态词卡索引。
## 三种学习方式

| `study_mode` | 目标 | 练习标准 |
| --- | --- | --- |
| `production` | 主动产出 | 能用自己的话解释，并在写作或口语中自然使用 |
| `recognition` | 阅读识别 | 能在上下文中快速认出，不强求立即主动使用 |
| `phrase` | 整块提取 | 把固定搭配作为一个单位回忆和造句 |

不要给 136 个词同样的学习投入。先把高频、跨场景、能提升表达的词练到可产出；专业名词和低频词先达到快速识别。

## 学习闭环

1. **保留证据**：记录遇见形式、完整原句、文章标题或 URL、页码或视频时间点。
2. **规范化**：去掉大小写和标点噪声，恢复 lemma；派生词保留为自己的词条，不强行改成词根。
3. **先搜再建卡**：用索引、`Ctrl+O` 和全文搜索查重；已有 canonical card 就追加语境与计数，没有才创建。
4. **当天提取**：先看中文或场景回忆英文，再反向解释英英定义。
5. **间隔复测**：建议在 1、3、7、14、30 天后复测，根据实际表现调整 `next_review`。
6. **主动应用**：为 `production` 和 `phrase` 写自己的句子或短段落；只抄例句不算掌握。
7. **周复盘**：升级真正会用的词，降级总是混淆的词，并删除无意义的复习负担，而不是删除词卡。

## 当前批次

- 原始捕获：2026-07-21 生词记录
- 原始记录：137 条
- canonical cards：136 张（`testimony` 与 `testimonies` 合并；`bore` 已按真实语境归入 `bear`）
- 多词表达：8 个
- 真题映射：136 条已回看原卷页面；其中完形 46 条、阅读 90 条
- 来源异常：`echo chamber` 未在整卷出现，保留为 `source_mismatch` 衍生概念
- 重复优先级：[testimony](testimony.html) 同批出现两次，已提升为 `high`

## 全部词卡

> [!note] 交互式数据库请在私有 Obsidian Vault 中查看；公开页使用下方静态词卡索引。
## 公开网页边界

本模块的非敏感词卡可使用 `publish: true` 进入公开学习站点。公开导出器仍会硬性拒绝 `00_Inbox/`、`账单/`、`日记/`、`生活/`、`Attachments/`、`_System/`、`.obsidian/`、`Archive/` 和任何 `sensitive: true` 笔记。完整私有 Vault 不会直接发布。
