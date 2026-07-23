# 词间 · Lexicon Garden

这是由私有 Obsidian Vault 经过严格白名单导出的公开学习子集。公开仓库只包含已经确认 `publish: true` 的非敏感学习笔记和静态站点代码；完整 Vault、收件箱、账单、日记、生活笔记、附件与插件配置不进入本仓库。

## 本地预览

```powershell
python -m pip install -r requirements.txt
python build.py --output dist --base-url /
python -m http.server 8000 --directory dist
```

浏览器打开 <http://127.0.0.1:8000/>。成功信号：首页显示词卡数量，搜索、学习方式筛选、随机词卡和详情页均可使用。

`--base-url` 必须与部署路径一致：根域名使用 `/`，项目站点使用 `/仓库名/`。GitHub Actions 会从 Pages 配置读取实际路径，因此同时兼容项目站点、`<owner>.github.io` 仓库与自定义域名。

## 从私有 Vault 重新导出

首次在私有 Vault 根目录运行时，显式使用 `-Bootstrap` 创建隔离的 `.venv-site` 并按锁定的 `requirements.txt` 安装依赖；脚本不会静默修改全局 Python：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File _System\Scripts\Export-PublicSite.ps1 -Bootstrap -Check
```

以后先执行只读检查，再导出并按实际部署路径构建：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File _System\Scripts\Export-PublicSite.ps1 -Check
powershell -NoProfile -ExecutionPolicy Bypass -File _System\Scripts\Export-PublicSite.ps1 -OutputPath "D:\path\to\public-repo" -Build -BaseUrl "/repository-name/"
```

成功信号：检查结果包含 `"ok": true`，构建后的 `dist/` 中存在首页、词卡详情、搜索索引与 `assets/favicon.svg`。

## 架构

- `content/manifest.json`：公开清单，不含私有源路径。
- `content/*.md`：经过 Wikilink 与隐私净化的公开正文。
- `build.py`：静态构建器，禁用原始 HTML。
- `templates/`：页面模板。
- `assets/`：样式与交互。
- `.github/workflows/deploy-pages.yml`：GitHub Pages 构建与部署。

内容更新应从私有 Vault 重新导出，不要把私人笔记直接复制到本仓库。导出器只复制明确列入白名单的站点源文件，并在写入公开仓库前扫描完整暂存树；已有公开仓库的 `.git/` 会保留，其余内容会由新导出结果完整替换，避免陈旧文件残留。
