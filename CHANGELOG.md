# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## 3.0.0 — 2026-10-01

### 新增

- **`gender` 一键切换性别**：只改这一个字段，代词（she / he / they）、人物总称（woman / man / figure）、年龄从句主语、中文代词（她 / 他 / TA）全部自动派生。
- **令牌体系**：`{s}` `{S}` `{p}` `{P}` `{o}` `{T}` 引用代词，`{V:原形}` 做动词第三人称单数变位。`neutral`（they）必须用 `{V:原形}`，否则会渲染出 `They holds` 这类病句。
- 新字段 **`hair_style`**（发型从句的谓语部分）与 **`weapon_hand`**（哪只手持械）。
- 第二个新角色示范 `凌霜`，演示 `hair_style` 高束马尾 / `weapon_hand` 右手 / `crown` 留空＝不戴头饰。

### 修复

- 骨架里 **15 处 `she` / `her` 写死** → 全部改为派生占位符。此前只把人物总称做成了变量，代词没换，换成男相会渲染出 `a young ... man ... over her shoulder`。
- 发型与持械的手也是写死的（`half pinned up and half loose` / 未指定左右手）→ 分别抽成 `hair_style`、`weapon_hand`。

## 2.0.0 — 2026-10-01

### 修复

- **换了角色头上照样长花冠**：模板第 7 段（后视图）与第 8 段（表情板）把 `flower crown` 当成了骨架常量，而 `{{crown}}` 变量只在第 5 段被引用。根因是抽模板时，4 份样例恰好都是花冠角色，**样例共有的属性被误当常量写死**。
- 同类写死一并查出：`moon-white`（内衬底色）、人物总称与指代、以及「`a {{crown}}, {{earrings}} and {{ankle}}`」这个固定三项列举（任一槽留空就蹦断句）。

### 新增

- **`FIXATION_WATCH` 写死探针**：骨架里出现角色相关词或代词（`flower crown` / `moon-white` / `she` / `her` …）→ `--check` 直接返回码 2。
- 派生字段：`crown_noun` / `crown_back_phrase` / `crown_share_phrase` / `accessories_clause`。
- **三处可空槽** `crown` / `earrings` / `ankle`：留空即「这位不戴」，三处从句自动摘掉，不留空位也不蹦断句。
- `verify_presets.py` 从 1 关扩到 **3 关**：原稿一致 / 换装成立 / 防线自检。

## 1.0.0 — 2026-10-01

### 新增

- 从 4 份人工验收通过的提示词原稿中，用逐段对齐比对机械分离出「常量骨架」与「变量槽」，得出 12 段定稿模板与变量契约。
- `scripts/render_prompt.py`：JSON → 提示词，带体检（缺字段 / 数组项数 / 表情重名 / HEX 格式 / 占位符残留 / 长度门槛）与渲染。
- `scripts/presets/`：紫嫣 / 绯枫 / 禾晏 / 桃夭 四套验收变量。
- `scripts/verify_presets.py`：渲染结果与验收原稿逐字符比对。
