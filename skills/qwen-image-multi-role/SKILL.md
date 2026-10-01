---
name: qwen-image-multi-role
description: 多角色多视图提示词生成器（Qwen-Image 2.1 英文提示词）。把一段人物设定编译成一份「竖版多面板角色参考卡」英文提示词 —— 左侧画境全身立绘 + 右侧三块半透明面板（三视图 4 格 / 表情展示 4 格 / 细节展示 8 格）+ 底部通栏三栏（色彩搭配 / 角色设定 / 背景设定）。内置定稿模板、79 个变量字段（`gender` 一键切换性别与代词；`hair_style` 换发型、`weapon_hand` 定哪只手持械；`crown` / `earrings` / `ankle` 可整项留空）、4 套已验收角色预设（紫嫣 / 绯枫 / 禾晏 / 桃夭）与渲染脚本（JSON → 提示词，硬校验零残留占位符 + 三关回归 + 写死探针）。触发词：多角色提示词、多视图角色卡提示词、角色多视图、按紫嫣那种多视图再做一张、换个人物再做一张、批量出角色卡提示词、qwen-image-multi-role、multi-view character card prompt、give me the multi-view prompt for <角色名>。
agent_created: true
---

# qwen-image-multi-role —— 多角色多视图提示词机

**输入一段人物设定，输出一份可直接粘贴出图的英文提示词。** 版式、格数、格名、文字串纪律、中文文案公式、渲染脚本全部内置；换角色只需要换变量，不动模板。

本技能已被验证：用 `scripts/presets/` 里 4 套变量渲染出来的提示词，与用户验收通过的 4 份原稿**逐字符完全一致**（忽略换行形式）。所以**新角色只要把变量填对，版式就不会跑偏**。

---

## 0. 30 秒上手（新会话照抄）

### 一条命令出成品

```bash
# 在本技能目录（含 SKILL.md 的那一层）内执行
PY="python"        # 任意 Python 3；脚本零第三方依赖，只用标准库

# ① 体检（改完变量先跑这个，0 秒知道缺什么）
"$PY" scripts/render_prompt.py --json 我的角色.json --check

# ② 出行（单行版：换行写成字面 \n，就是可以直接粘进生图节点的那种）
"$PY" scripts/render_prompt.py --json 我的角色.json --escape --out 我的角色多视图.txt

# ③ 想要分段可读版给人看：去掉 --escape
"$PY" scripts/render_prompt.py --json 我的角色.json
```

脚本用 `__file__` 自定位模板与预设，**安装到哪个目录都能跑，不需要任何绝对路径**。
只需保证调用时的**工作目录在本技能目录内**（`cd` 过去即可）；模板另有 `--template` 可显式覆盖。

### 三条路径，先选一条

| 你要做什么 | 走哪条路 | 怎么做 |
|---|---|---|
| **换一个新角色**（最常用） | **路径 A · 改预设**（最稳） | 复制 `scripts/presets/zhiyan.json` → 改值 → 体检 → 出行。**不要碰模板** |
| 主题色系完全没参考 | 路径 B · 从零派生 | 按 §3 的推导链，从「主题三件套」派生全部 79 个字段 |
| 只想看看效果 / 要现成的 | 路径 C · 用预设 | `--preset zhiyan`（或 feifeng / heyan / taoyao），`--list-presets` 可列全 |

### 被调用契约（父智能体 → 本技能）

**调用方至少要给**：角色名（必）+ 任意几条设定（气质 / 主题色倾向 / 世界观身份 / 武器 / 年龄感）。

**本技能必须回**（三件套，缺一不可）：

1. `<角色名>变量.json` —— 完整 79 字段变量表
2. `<角色名>多视图.txt` —— **单行 `\n` 版提示词**（可直接粘贴出图的那一份）
3. 体检报告 + **假设清单**（哪些槽是我替你定的、依据是什么；没给的信息不要编造，宁可整行省略或按默认范式补，并明说是默认）

> 没给的字段**按 §3 的公式派生**，不要留空、不要写 `TODO`。派生了什么，在假设清单里列清楚。

---

## 1. 这张卡长什么样（版面地图 · 硬指标）

```
┌────────────────────────────────┬──────────────────────────────┐
│ 竖排书法名 + 朱红方印              │ 三视图  4 格                  │
│ + 圆medallion单字 + 两列竖排题词   │ 正视图/半侧视图/侧视图/后视图   │
│                                ├──────────────────────────────┤
│ 画境 scene（渐变天 / 垂枝 / 漂浮物  │ 表情展示  4 格                │
│ / 月晕 / 远山+亭 / 雾+浮尘）       ├──────────────────────────────┤
│                                │ 细节展示  2 行 × 4 格 = 8 格   │
│ 全身立绘（同一人）                │ 上排：发饰/耳饰/腰饰/武器饰     │
│ 脚下淡影                         │ 下排：袖摆/裙摆/鞋履/材质       │
├────────────────────────────────┴──────────────────────────────┤
│ 色彩搭配            │ 角色设定               │ 背景设定           │
│ 6 竖色块(HEX+中文名) │ 6 行属性 + 居中联句      │ 背景故事段落       │
│ + 3 行色诗          │ + 武器小图             │ + 右下角落款       │
└───────────────────────────────────────────────────────────────┘
```

| 硬指标 | 值 | 说明 |
|---|---|---|
| 模块数 | **6** | 主视觉 / 三视图 / 表情展示 / 细节展示 / 色彩搭配 / 角色设定 / 背景设定（后三块同属底栏） |
| 右侧多格区 | **4 行** | 三视图 1 行 + 表情 1 行 + 细节 2 行 |
| 三视图格数 | **4** | 格名固定：`正视图` `半侧视图` `侧视图` `后视图` |
| 表情格数 | **4** | 格名 = `expressions[0..3]`，四格互不相同 |
| 细节格数 | **8** | 两行四列，八个图注互不相同 |
| 底栏栏数 | **3** | 等宽，**任一栏都不许空着** |
| 色彩搭配 | **6 色** | 竖色块，每个写 `#HEX 中文名` |
| 画幅 | **竖版** | 卡片是「tall」；工作流里记得同时设成竖版 |
| 图内文字 | **一律纯中文** | 只有「图片怎么画」的叙述是英文 |
| 提示词长度 | **约 9.7k 字符** | 越过 13.5k 就要删冗余，见 §5 |

---

## 2. 变量契约（79 字段 / 100 取值 · 分组速查）

> 口径说明（三套数，别混）：**69 个平铺字段 + 4 条表情描述 + 6 个数组 = 79 个字段**；数组逐项展开后是 **100 个取值**。
> 另有 **10 个派生字段**（`crown_noun` / `crown_back_phrase` / `crown_share_phrase` / `accessories_clause`，以及代词 `pron_subj` / `pron_subj_cap` / `pron_poss` / `pron_poss_cap` / `pron_obj` / `pron_cn`）由脚本从 `crown`、`gender` 算出，**不用写进 JSON**，但模板会引用它们，所以脚本的占位符核对清单是 **89 项**。
> `--init` 生成的空白模板共 **81 个键** = 上面 79 个字段 + `preset_id` / `theme_label_cn` 两个纯备注键（不参与渲染）。
> 其中 **`gender` 是换性别的唯一入口**，**`crown` / `earrings` / `ankle` 三个槽可以整项留空**，见 §2.4。

> 左列是 JSON 字段名（也是模板里的占位符名）；中列写「这个槽该写什么」；右列是紫嫣的实际取值，作为语感参照。
> **值一律英文小写短语**（中文只出现在图内文字类的槽里：名字、题词、格名、属性栏、背景故事、落款）。

### 2.1 题款（图内中文）

| 字段 | 写什么 | 紫嫣 |
|---|---|---|
| `name_cn` | 角色名（竖排大字） | 紫嫣 |
| `seal_cn` | 朱红方印上的字，通常=名字 | 紫嫣 |
| `medallion_char` | 圆形徽记里的**单字**，取名字里最有画面感的那个字 | 嫣 |
| `verse1` `verse2` | 两列竖排题词，公式见 §3.3 | 一箫引万蝶，／半梦借君眠。 |

### 2.2 纸与版（决定整张卡的色底）

| 字段 | 写什么 | 紫嫣 |
|---|---|---|
| `paper_sheet` | 第 1 段的纸名，**含形容词**，可带 `-tinted` | pale lilac |
| `paper_whisper` | 纸底「一丝什么色」 | lilac |
| `ground_tint` | 第 12 段的纸色，**必须带 `-tinted` 后缀**写法 | lilac |
| `watermark` | 暗纹图案，**3~6 个名词串** | wisteria vine and butterflies |
| `watermark_noun` | 暗纹的**简称**（右侧面板句里用） | vine |
| `border_color` | 全卡细线框 / 面板边线颜色 | violet |
| `stain_color` | 四角水渍颜色 | lilac |
| `shadow_color` | 立绘脚下淡影颜色（可与主色不同） | violet |

### 2.3 画境（左半张的景）

| 字段 | 写什么 | 紫嫣 |
|---|---|---|
| `scene_name` | `painted ...` 开头的画境名 | painted night garden |
| `gradient` | 天空渐变**整句**：`A at the top to a deeper B lower down` | pale lilac at the top to a deeper violet lower down |
| `hanging_elements` | 上方垂下来的枝条（可两种） | wisteria branches |
| `hanging_short` | 立绘句里的短称 | wisteria |
| `drifting_elements` | 漂浮物**带现在分词** | drifting petals |
| `drifting_short` | 越界句里的短称（去掉分词） | petals |
| `moon_halo` | 月亮 + 月晕整句 | a hazy full moon ringed by a violet halo |
| `backdrop` | 远景剪影整句（远山 + 亭，可加粮仓等） | silhouetted mountain ridges and a small tiered Chinese pavilion standing behind the figure |
| `motes` | 贴近地面的浮尘 | violet motes |

### 2.4 人物（同一人的全部穿戴都要在这里定死）

| 字段 | 写什么 | 紫嫣 |
|---|---|---|
| `gender` | **换性别的唯一入口**：`female`（默认）/ `male` / `neutral`。代词、人物总称、年龄从句主语一起跟着换 | female |
| `subject_desc` | **人物总称**（第 1 段句首）。**留空即按 `gender` 自动派生**；只有「妖族 / 少年 / 特殊身份」这类才需要手填 | a young Chinese fantasy immortal woman |
| `subject_ref` | 第 6 段的**指代**。留空即按 `gender` 自动派生 | this woman |
| `age_desc` | 年龄短语（不带标点） | likely in her late teens |
| `age_phrase` | **年龄从句整句**（可省，脚本按 `a slender young woman, {age_desc}` 自动拼；要用「of about twenty」式写法就显式给） | a slender young woman, likely in her late teens |
| `hair_color` | 发色。**惯例是 `pale {主题}-silver`，但不是铁律**：墨发写 `ink-black` | pale lilac-silver |
| `hair_style` | 发型从句的谓语部分。**默认半盘半散（= 4 份原稿的写法）**；「gathered up into a high ponytail」/ 双螺 / 全散发直接覆盖 | half pinned up and half loose |
| `hair_ornaments` | 发饰 = 主题花枝 + 银质别针。额间印记这类「头部特征」也挂这里 | small wisteria sprigs and silver butterfly pins |
| `robe_color` | 外纱的**一个词**颜色 | violet |
| `robe_gradient` | 由胸至裙裾的渐变整句 | pale lilac at the chest to saturated violet at the trailing hem |
| `sash` | 腰带 = 主题物 + 链/铃 | wisteria blossoms and silver chain |
| `underrobe_color` | 内衬底色（默认 `moon-white`，想换直接覆盖） | moon-white |
| `crown` | 头饰。**可以整项留空**（留空 = 不戴头饰） | wisteria flower crown |
| `earrings` | 耳饰（可带主题色前缀）。**可留空** | butterfly-wing silver earrings |
| `ankle` | 踝饰（银 / 金 二选一，与整体金属统一）。**可留空** | silver ankle ornaments |

> **`crown` / `earrings` / `ankle` 是全卡仅有的三个可空槽。** 留空后第 5 段的穿戴句、第 7 段后视图的 `the back of …`、第 8 段表情板的 `one …` 都会**自动摘掉对应从句**，既不留空位也不蹦断句。
> **头饰写法有要求**：`crown` 要以「修饰语 + 头饰名词」收尾（`flower crown` / `hairpin` / `circlet` / `tiara` / `headband` / `helmet` …），脚本据此派生 `crown_noun` 供后视图与表情板引用。写成 `crown of white jade` 这种不以名词收尾的形式会触发告警，后视图只能退化成取末词。

> **换性别只改 `gender` 一个字段**，其余全自动：

| `gender` | 主格 | 所有格 | 宾格 | 中文 | 人物总称 / 指代 | 年龄从句主语 |
|---|---|---|---|---|---|---|
| `female`（默认） | she | her | her | 她 | …immortal **woman** / this **woman** | a slender young **woman** |
| `male` | he | his | him | 他 | …immortal **man** / this **man** | a slender young **man** |
| `neutral` | they | their | them | TA | …immortal **figure** / this **figure** | a slender young **figure** |

> **自己写的文案要跟着换性别，就用令牌**（渲染前统一替换；模板字段和你填的自由文本都适用）：

| 令牌 | 含义 | female | male | neutral |
|---|---|---|---|---|
| `{s}` / `{S}` | 主格（句首大写） | she / She | he / He | they / They |
| `{p}` / `{P}` | 所有格（句首大写） | her / Her | his / His | their / Their |
| `{o}` | 宾格 | her | him | them |
| `{T}` | 中文代词 | 她 | 他 | TA |
| `{V:原形}` | **动词第三人称单数**，脚本自动取舍 | 原形+s | 原形+s | 原形（they 配原形） |

> 例：`hold_action` 写 `{V:hold} a white jade xiao flute raised before {o}`；`age_desc` 写 `likely in {p} late teens`；`hold_tail` 写 `raised before {p} lips`。
> `{V:原形}` 内置常见不规则（be→is/are、have→has/have、do→does/do、go→goes/go）与 -s / -es / -y→-ies 规则。**`neutral` 必须用它**，否则会渲染出 `They holds` 这种病句。
> **直接写死 `her` / `she` 不报错、但会错**：脚本会告警提醒你改成令牌。4 套预设与素雪都已改用令牌，所以它们能被整体翻成男相 / 中性。

### 2.5 武器与动作（换手是重灾区，见 §5）

| 字段 | 写什么 | 紫嫣 |
|---|---|---|
| `weapon_hand` | 持械的那只手。**默认 `hand`（不指定左右）**；写 `right hand` / `left hand` 才能锁定 | hand |
| `weapon_noun` | **单个名词**：flute / sword / fan / umbrella / pipa / needle… | flute |
| `hold_action` | 立绘句里的持械动作整句；**有名字的兵器要把名字用双引号带上** | holds a white jade xiao flute raised before her |
| `hold_tail` | 三视图句里的动作尾巴（`raised to the lips` / `raised before her` / `raised before her lips`） | raised to the lips |
| `weapon_charm` | 兵器上挂的坠子整句（挂在哪儿要写清：lower end / hilt / handle） | a violet crystal butterfly charm hanging from its lower end |
| `companions` | 环绕的伴生（蝶 / 雀 / 鹤 / 萤 / 云） | violet butterflies |

### 2.6 格名与格内描述

| 字段 | 写什么 | 紫嫣 |
|---|---|---|
| `expressions[0..3]` | 四个表情名，公式见 §3.3 | 慵懒浅笑 / 垂眸沉思 / 微醺醉意 / 侧颜回盼 |
| `expr_desc_1..4` | 四段英文表情描述。**第 1 条按角色气质换形容词**（lazy / bright / warm / cool），第 2~4 条是全套固定范式，照抄 | — |
| `detail_upper[0..3]` | 上排四格：`发饰细节` / `{主题耳饰}` / `腰饰细节` / `{武器}饰细节` | 发饰细节 / 蝶翼耳饰 / 腰饰细节 / 首饰细节 |
| `detail_lower[0..3]` | 下排四格**固定不变** | 袖摆细节 / 裙摆细节 / 鞋履细节 / 材质细节 |

### 2.7 底栏三栏

| 字段 | 写什么 | 紫嫣 |
|---|---|---|
| `colors[0..5]` | 六个 `{hex, cn, en}`：**第 1 个固定是月白/米白**，后面从浅到深 | `#F7F5FB 月白 moon white` … `#6B5A8E 暮山紫 dusk violet` |
| `color_verse[0..3]` | 色块下三行色诗，**固定句式** | 幻蝶如梦，／我为你，／长守紫藤。 |
| `profile[0..5]` | 属性栏六行，**行首标签固定**：`姓名：` `身份：` `年龄：` `性格：` `喜好：` `武器：` | 姓名：紫嫣／身份：幻蝶灵境·守梦人／年龄：十九／性格：慵懒散漫，清醒护短／喜好：酿紫藤花酒、收集众生梦境、雨中吹箫／武器：幻蝶玉箫·青眠 |
| `couplet` | 居中联句，**全套固定不改** | 我本无心，只因你入梦，便留了心。 |
| `weapon_drawing` | 武器小图整句 | a small drawing of the white jade flute |
| `background_text` | 背景故事整段，公式见 §3.3，**建议 100 字以上**（底栏高度靠内容撑） | — |
| `signature` | 右下角落款，**固定句式** | —— 一箫一蝶一浮生，梦里不知身是客。 |

### 2.8 收束

| 字段 | 写什么 | 紫嫣 |
|---|---|---|
| `vine` | 沿右边缘垂下的藤 | wisteria vine |
| `drop` | 藤上掉落物 | petals |
| `lighting` | 光源整句 | the violet moon behind thin cloud |
| `palette` | 三个颜色名（英文），锁住整卡色域 | pale lilac, wisteria violet and moon white |
| `mood` | 情绪两个词 | dreamlike, quietly melancholy |

---

## 3. 从零派生一个新角色（这套方法的核心）

### 3.1 第一步：定「主题三件套」

先把角色压缩成三个词，全部后续槽位都从它们长出来：

| 三件套 | 含义 | 例 |
|---|---|---|
| **主题物** | 一种花木 + 一个主题色 | 紫藤·紫 / 丹枫·红 / 金稻·黄 / 桃树·粉 |
| **兵器** | 一个**单字名词** | 箫 / 剑 / 笛 / 扇 / 伞 |
| **境界身份** | `{境界}灵境·守{单字}人` | 幻蝶灵境·守梦人 |

### 3.2 第二步：从三件套派生出「名词组」

一条链，不改结构只换词：

```
主题物 → watermark（暗纹）/ motes（浮尘）/ companions（伴生）/ crown（花冠）
       → sash（腰带）/ earrings（耳饰）/ vine（垂藤）/ drop（落物）
主题色 → paper_sheet / paper_whisper / ground_tint / border_color / stain_color
       → shadow_color / gradient / moon_halo / robe_color / robe_gradient / palette
兵器   → weapon_noun / hold_action / hold_tail / weapon_charm / weapon_drawing
       → detail_upper[3]（{兵器}饰细节）
```

**色板 6 色的取法**（保证不像拼的）：

1. **第 1 色固定**：月白 `#F7F5FB`~`#FFF7FA` 之间（冷紫底更灰、粉底更暖白、黄底更米）。
2. **第 2~5 色**：主题色的「粉白 → 浅 → 中 → 深」四档，色相基本不动、饱和度与明度递进。
3. **第 6 色**：最深的**暮色版**，命名惯例 `暮{山/金/粉}{原色}`。
4. **命名惯例**：第 1 个叫 `月白`（暖黄系可叫 `米白`），末端两个用「暮」字开头。
5. `en` 用色名的直译（moon white / frost blue / slate teal…），`cn` 用中文雅名。

### 3.3 第三步：四段中文文案（**全部是填空题**）

```
题词    verse1 = "一{兵器动作}引{伴生单字}，"        verse2 = "半梦借君眠。"
        紫嫣：一箫引万蝶，/ 半梦借君眠。
        绯枫：一叶燃秋山，/ 半剑寄君安。
色诗    color_verse = ["{伴生}如梦，", "我为你，", "长守{主题物}。"]
        紫嫣：幻蝶如梦，/ 我为你，/ 长守紫藤。
落款    signature = "—— 一{兵器}一{伴生单字}一浮生，梦里不知身是客。"
        紫嫣：—— 一箫一蝶一浮生，梦里不知身是客。
表情    ["{气质}浅笑", "垂眸{主题动作}", "微醺{主题饮品}", "侧颜回盼"]
        紫嫣：慵懒浅笑 / 垂眸沉思 / 微醺醉意 / 侧颜回盼
        禾晏：温软浅笑 / 垂眸听风 / 微醺桂酿 / 侧颜回盼
属性栏  profile = ["姓名：X", "身份：{境界}灵境·守{字}人", "年龄：{中文数字}",
                  "性格：{表}，{里}", "喜好：{三到四件带主题的事}",
                  "武器：{兵器雅名}·{单字兵器名}"]
        紫嫣：武器：幻蝶玉箫·青眠
背景段  background_text =
        "{名}，{境界}灵境的守{字}人。她以{兵器}引{伴生}，以{主题物单字}为舟，渡人{动}，
         却从不{否定}。看似{表}、游戏人间，实则{里}，只肯在{场景}独酌。
         她在灵境中种满{主题物}，引万千{伴生}为伴，唯独等一个{一类人}。
         {兵器}声起时，{奇观一}；{兵器}声落处，{奇观二}无痕。"
```

### 3.4 四套已验收角色的取值矩阵（照矩阵推新角色就不会跑偏）

| 槽位 | 紫嫣 | 绯枫 | 禾晏 | 桃夭 |
|---|---|---|---|---|
| 主题 / 兵器 / 身份 | 紫藤·箫·守梦人 | 丹枫·剑·守秋人 | 金稻·笛·守穗人 | 桃树·扇·牵缘人 |
| `paper_sheet` | pale lilac | pale maple-red-tinted | warm rice-yellow-tinted | pale peach-pink-tinted |
| `watermark` | wisteria vine and butterflies | maple leaves, crimson butterflies and wild geese | rice ears, golden sparrows and wheat waves | peach blossoms, pink butterflies and trailing vines |
| `watermark_noun` | vine | maple-leaf | rice-ear | peach-blossom |
| `border_color` | violet | crimson | golden-brown | rose-pink |
| `scene_name` | painted night garden | painted autumn maple dreamscape | painted harvest valley dreamscape | painted peach dream flower realm |
| `hair_color` | pale lilac-silver | pale maple-silver | pale rice-silver | pale peach-silver |
| `sash` | wisteria blossoms and silver chain | maple leaves and silver chain | wheat ears and bronze bells | peach blossoms and silver chain |
| `earrings` | butterfly-wing silver earrings | crimson butterfly-wing silver earrings | golden sparrow earrings | pink butterfly-wing silver earrings |
| `ankle` | silver | silver | gold | silver |
| `companions` | violet butterflies | crimson butterflies | golden sparrows | pink butterflies |
| `hold_action` | holds a white jade xiao flute raised before her | holds a crimson jade sword "霜秋" raised before her | holds a golden rice-ear jade flute "丰眠" raised before her lips | holds a peach-blossom jade fan "绯梦" raised before her lips |
| `hold_tail` | raised to the lips | raised before her | raised to the lips | raised before her lips |
| `detail_upper[3]` | 首饰细节 | 剑饰细节 | 笛子细节 | 扇子细节 |
| 色板（浅→深） | 月白→烟霞紫→兰若紫→星辰紫→琉璃紫→暮山紫 | 月白→霜枫粉→霞枫红→丹砂红→赤枫红→暮山红 | 米白→稻浪黄→秋收黄→金桂黄→琥珀金→暮金褐 | 月白→樱粉→桃夭粉→胭脂粉→玫瑰粉→暮粉紫 |
| `mood` | dreamlike, quietly melancholy | bright, quietly melancholy | warm, quietly contented | romantic, quietly wistful |

---

## 4. 渲染与体检

```bash
"$PY" "$SK/scripts/render_prompt.py" --json x.json --check        # 只体检；返回码 2 = 不通过
"$PY" "$SK/scripts/render_prompt.py" --json x.json --escape       # 单行 \n 版（要交付的那份）
"$PY" "$SK/scripts/render_prompt.py" --json x.json               # 12 段可读版
"$PY" "$SK/scripts/render_prompt.py" --preset heyan --escape      # 内置预设
"$PY" "$SK/scripts/render_prompt.py" --list-presets
"$PY" "$SK/scripts/render_prompt.py" --init > new_char.json       # 生成空白变量模板
```

**脚本会自动拦下这些错**（所以先跑 `--check` 再改提示词，别用眼睛找）：

- 缺字段 / 数组项数不对（`expressions` 4、`detail_upper` 4、`detail_lower` 4、`colors` 6、`color_verse` 3、`profile` 6）
- 四个表情名重复、四段表情描述重复、八个细节图注重复
- `hex` 不是 `#RRGGBB`
- 模板占位符取不到值、渲染后残留 `{{ }}` 或 `{V:...}` / 代词令牌
- 值里混进 `{{ }}` 或单引号
- 图注里带武器字又不含「细节」（会被模型字面化成兵器）
- 总长度越过 **13500 字符**（版面级崩坏门槛）
- **模板骨架里写死了角色相关词或代词**（写死探针；清单与修法见 §6.6）
- **性别与代词对不上**（如 `gender=male` 却还在文案里写 `her`；脚本会点名列出残留词）

### 4.1 三关回归（改完模板必跑）

```bash
"$PY" "$SK/scripts/verify_presets.py"     # 三关全过才算改对，返回码 2 = 有一关没过
```

| 关卡 | 验的是什么 | 为什么必须有 |
|---|---|---|
| 第 1 关 | 4 套预设渲染结果与验收原稿**逐字符一致** | 证明你没把已通过的东西改坏 |
| 第 2 关 | 摘掉头饰、换非花冠头饰、翻成男相 / 中性后句子仍成立（31 项） | 4 份原稿全是花冠女性，**光"一致"证明不了模板对别的角色也对** |
| 第 3 关 | 故意把 `flower crown` / `her` 塞回骨架、再写入非法令牌 `{q}`，三样都必须被拦 | 证明防线还活着，不是摆设 |

---

## 5. 硬约束（违反一条就重写，不要「试试看」）

1. **同一个人**：卡上所有图（大立绘 + 4 个三视图 + 4 个头肩特写）必须**同脸、同发型、同服装、同武器**；只有角度 / 裁剪 / 表情变。
2. **不换手**：同一只手持械，另一只空手放松搭在腰带上。模板已写死「不得换手」的负面句，**别删**。
3. **三视图旋转必须递进**：`正视图` = 双眼可见 → `半侧视图` = 45°，双眼仍可见（远眼靠近脸颊外缘）→ `侧视图` = **平面 90°，只有一只眼可见，另一只被鼻梁完全遮住** → `后视图` = 无眼可见。**第三格必须是平面侧视，不是四分之三侧。**
4. **表情 4 格必须各异**，且与图注对得上；表情块内**不许出现手、不许出现武器**。
5. **细节 8 格部位互不相同**，方形裁剪、尺寸一致。
6. **底栏三等宽、任一栏不许空**；空栏要补内容（文字或插图），**不要写「用装饰留白填充」**——模型会真的留白。
7. **边缘闭合**：右侧三块面板的下沿与左侧立绘的脚落在**同一条水平线**；底栏通到左右边缘；整张卡闭合为一个矩形，中间不留空白带。
8. **图内文字一律纯中文**，且**只有模板里点名的那几处**（名字、印章、徽记字母、题词、三视图格名、表情格名、细节格名、底栏三栏标题、6 个色值+色名、3 行色诗、6 行属性、联句、背景段、落款）。**多一个字都是在给模型添乱**：文字串越多，小字越先崩。
9. **长度纪律**：成品约 9.7k 字符。**想加句子，先删等量冗余**——实测越过 13.5k 就容易出「多出一格 / 区块标题重名 / 整块被画两遍」。

---

## 6. 已知崩坏点与修法（换角色后必须重新确认的三处）

### 6.1 第三格画成四分之三侧（最常见）

**别描述「半侧 / 侧面」这种连续量**，模型无法自查。模板里已经把它翻译成**可数的离散量**：「只看得见几只眼睛」= 2 → 2（透视）→ 1 → 0。**这四句是定稿，不要改**。若确实退回，检查是不是被别处新增的「角度/朝向」描述干扰了。

### 6.2 细节格被吞（一格拍成别的东西）

两条通用规律，改角色时要顺着检查：

- **多数派会吞掉少数派**：一行里只有一格类型不同（例如三格饰物 + 一格人脸局部），必须**单独给那一格声明类型**，否则整行会被统一解释。
- **饰物格会被「最近的头饰」吞掉**：凡饰物格都要**点明它挂在身上哪里**（发簪→插在发髻里；腰封→系在自然腰线上），只说物件名模型会当成独立小物乱拍。

**定位一律走「格名」不走序数**：「第 3 格」会数错（实测内容与标签互换、整块多画一行），要写 **`the cell captioned "眉间剑印" is the only …`** —— 引号里的固定文本不会漂。

### 6.3 左侧出现一块硬边（「像拼的 / 没融入」）

根因不是「边缘怎么处理」，而是**「这张卡上有几张画面」**：只要描述里出现「某半张 + 一幅画 / 一块绘制范围」，模型就会先画出那块画面连同它的一圈边。修法是**取消「一块画面」这个说法**：改成**整卡一张连续背景**，主体是它最前的一层，右侧三块面板是**浮在同一张背景上的浅色板**。注意：把边界「羽化/压到极低」只是让它消失，**不等于连成一体**。

### 6.4 底栏被压成一条细字幕条

模型对「底部信息带」的先验很顽固，加「请画高一点」无效。三招按顺序用：

1. 写相对锚点：`每个栏都是一个高耸面板，高度约为自身宽度的五分之四`（数学上≈最下两成）。
2. **用内容量撑**（最有效）：背景段写 100 字以上、属性栏六行写满、色板给足 6 色。
3. 实在上不去就如实告知这是执行上限，不要继续堆句子（会触发版面崩坏）。

### 6.5 三条通用纪律（迁移到任何新角色都成立）

- **把连续量翻译成离散量**：角度、距离、比例这些模型无法自查；「几只眼可见」「几个格子」「哪只手拿东西」它才能自检。
- **点名禁掉「最近的错误」，比描述「正确样子」有效**：「不是齐胸襦裙、不是高腰」比「落在自然腰线上」管用。
- **相对比较 > 绝对百分数**：给不了可数量，就挂到一个图内已有、位置稳定的参照物上（「约等于左侧立绘高度的三分之一」）。

### 6.6 换了角色，头上还戴着花冠 / 代词还是 she（骨架被写死）

**这不是「风格不对」，是模板 bug。** 已在 v2 修掉，但同类必然还会再犯，所以要记住判据。

起因：4 份验收原稿恰好都是花冠角色（藤 / 枫叶 / 稻穗 / 桃花），从它们抽模板时，`flower crown` 和骨架常量长得一模一样，于是被当常量写进了**两处** —— 第 7 段后视图的 `the back of the flower crown`、第 8 段表情板的 `one hairstyle, one flower crown and one framing`。`{{crown}}` 这个变量明明存在，却没在那两处被引用。结果换个不戴花冠的角色，卡上照样长出一顶花冠。

**同一病因的第二种表现**：骨架里还写死了 **15 处 `she` / `her`**。上一版只把人物总称换成了变量，代词没换 —— 改成男相就会渲染出 `a young ... man ... over her shoulder`。现已全部改为 `{{pron_subj}}` / `{{pron_poss}}` 等派生占位符，由 `gender` 一处分发。

**判据（一眼认同类问题）**：一句话里的某个名词，换个角色就说不通了，而它在模板里**不是** `{{占位符}}` —— 那就是写死。

**修法（两步，别只做第一步）**：

1. 该处改成占位符，并在 `render_prompt.py` 的 `COMPUTED_FIELDS` 里给它一条派生规则（本例：`crown` → `crown_noun` → `crown_back_phrase` / `crown_share_phrase`）。**派生要写在 `fill_defaults` 里，且必须在用户改值之后** —— 否则改 `crown` 不会带动从句。
2. **把那个词加进 `FIXATION_WATCH`**，从此骨架里一出现它就 `--check` 返回码 2。

已列入探针：`flower crown`、`moon-white`、`half pinned up`、`same hand`，以及代词词族 `she` / `her` / `hers` / `woman` / `man` / `girl` / `lady`（按整词匹配，不会误伤 `there` / `other`）。
**第三次发病（v3 已修）—— 发型与持械的手也被写死过**：骨架里原本写死 `{{pron_poss_cap}} {{hair_color}} hair is half pinned up and half loose, threaded with {{hair_ornaments}}`，碰到「墨发高束马尾」这类角色会渲染成半盘半散；另一处 `the same hand holds the {{weapon_noun}}` 不指定左右，让「右手紧握」这种硬要求落空。已分别参数化为 `{{hair_style}}` 与 `{{weapon_hand}}`，**默认值就是原文**，所以 4 份原稿仍逐字符一致。注意这类词的隐蔽之处：它们描述的是**通用属性**（手、头发），不像 `flower crown` 那样一眼就是角色专属，抽模板时最容易漏。

**每发现一次同类问题就往清单里加一条**，这是本技能唯一会自我进化的防线。

---

## 7. 批量做多个角色（一次出 N 张）

**保持不变**（改了会破坏系列感）：模板全文、6 模块版式、格名与格数、`couplet`、`detail_lower`、`expr_desc_2..4`、所有负面句。

**必须拉开的**：

| 维度 | 要求 |
|---|---|
| 主题色相 | 两两相隔 ≥ 60°（紫 / 红 / 黄 / 粉 / 蓝 / 青 / 绿），**同一色系不要连出两张** |
| 兵器名词 | 不重复（箫 / 剑 / 笛 / 扇 / 伞 / 琵琶 / 针…） |
| 伴生 | 不重复（蝶 / 雀 / 鹤 / 萤 / 雁 / 鹿…） |
| 主题物 | 不重复（藤 / 枫 / 稻 / 桃…），连带改暗纹、发饰、腰带、花冠、垂藤、落物 |
| `scene_name` | 不重复（夜园 / 秋山 / 丰谷 / 花境…） |
| 落款 | `一{X}一{Y}一浮生` 里两个单字都要换 |

**每张卡出图后逐格核对**：「标签说的 = 格子里画的」。**每改一版至少跑 3 次**（模型有随机性，单次不可信）。

---

## 8. 参考文件

```
qwen-image-multi-role/
├── SKILL.md                          ← 你正在读的这份（自包含，可直接被多智能体调用）
├── references/
│   ├── template-en.txt               ← 【单一事实源】12 段定稿模板，只改 {{占位符}}，不改字
│   ├── examples/
│   │   ├── 紫嫣角色多视图.txt           ← 用户验收通过的 4 份原稿（保留原始单行 \n 形态；
│   │   ├── 绯枫角色多视图.txt                紫嫣那份还带手工转义的 \"）
│   │   ├── 禾晏角色多视图.txt
│   │   ├── 桃夭角色多视图.txt
│   │   ├── 素雪变量.json               ← 新角色示范：冰雪蓝 · 纸伞 · 寒山灵境·守雪人
│   │   ├── 素雪角色多视图.txt                  （演示 `umbrella` 这个新兵器名词与「of about twenty」式年龄从句）
│   │   ├── 凌霜变量.json                ← 第 2 个新角色示范：冰霜蓝 · 剑 · 霜华灵境·守剑人
│   │   ├── 凌霜角色多视图.txt                  （演示 `hair_style` 高束马尾 / `weapon_hand` 右手 / `crown` 留空＝不戴头饰）
│   │   ├── 头饰槽修复对照.txt            ← 「写死 bug」修复对照：4 种头饰设定下的实际句式
│   │   └── 性别切换对照.txt              ← `gender` = female / male / neutral 三档逐句对照
└── scripts/
    ├── render_prompt.py               ← JSON → 提示词（体检 + 渲染 + 写死探针，零残留占位符）
    ├── verify_presets.py              ← 【改模板后必跑】三关回归：原稿一致 / 换装成立 / 写死被拦
    └── presets/
        ├── zhiyan.json  feifeng.json  heyan.json  taoyao.json   ← 4 套验收过的变量
```

**改版纪律**：要动版式，只改 `references/template-en.txt`；改完必须**回归验证**——用 4 个预设各渲染一次，与 `references/examples/` 的对应原稿逐字符比对（忽略空白与 `\"`），**必须 4/4 一致**，否则就是改坏了。
