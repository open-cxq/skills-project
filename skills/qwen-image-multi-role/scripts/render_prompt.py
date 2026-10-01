#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qwen-image-multi-role / render_prompt.py
========================================
把一份角色变量 JSON 渲染成 Qwen-Image 2.1 可直接出图的英文提示词。

用法：
  python render_prompt.py --preset zhiyan                 # 用内置预设（zhiyan/feifeng/heyan/taoyao）
  python render_prompt.py --json my_char.json             # 用自定义 JSON
  python render_prompt.py --json my.json --escape         # 单行版（换行写成字面 \n），最常用
  python render_prompt.py --json my.json --out prompt.txt --escape
  python render_prompt.py --json my.json --check          # 只体检、不渲染（返回码 0 通过 / 2 失败）
  python render_prompt.py --init > new_char.json          # 生成空白变量模板
  python render_prompt.py --list-presets

约定：
  * 模板文件默认取 ../references/template-en.txt（相对本脚本）。
  * JSON 字段名与模板里的 {{字段}} 一一对应；数组用 {{字段[0]}}，对象数组用 {{colors[0].hex}}。
  * 渲染完成后模板里不允许再残留 {{ }}；本脚本会硬校验。
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(HERE, "..", "references", "template-en.txt")
PRESET_DIR = os.path.join(HERE, "presets")

# ---------------------------------------------------------------- 字段契约

SCALAR_FIELDS = [
    "name_cn", "seal_cn", "medallion_char", "verse1", "verse2", "age_desc", "age_phrase",
    "gender", "subject_desc", "subject_ref",
    "paper_sheet", "paper_whisper", "ground_tint", "watermark", "watermark_noun",
    "border_color", "stain_color", "shadow_color",
    "scene_name", "gradient", "hanging_elements", "hanging_short", "drifting_elements",
    "drifting_short", "moon_halo", "backdrop", "motes",
    "hair_color", "hair_style", "hair_ornaments", "robe_color", "underrobe_color", "robe_gradient", "sash",
    "crown", "earrings", "ankle",
    "weapon_noun", "weapon_hand", "hold_action", "hold_tail", "weapon_charm", "companions",
    "detail_upper_1", "detail_upper_2", "detail_upper_3", "detail_upper_4",
    "detail_lower_1", "detail_lower_2", "detail_lower_3", "detail_lower_4",
    "color_verse_1", "color_verse_2", "color_verse_3",
    "profile_1", "profile_2", "profile_3", "profile_4", "profile_5", "profile_6",
    "couplet", "weapon_drawing", "background_text", "signature",
    "vine", "drop", "lighting", "palette", "mood",
]

# 可以整项留空：留空后相关从句会自动从提示词里消失，而不是留个空位或蹦出断句。
# —— 没有头饰 / 耳饰 / 踝饰的角色，把对应字段写成 "" 或直接删掉即可。
OMITTABLE_FIELDS = {"crown", "earrings", "ankle"}

# 由其它字段在渲染时算出来的字段（不写进 JSON，不参与"必填"校验）
COMPUTED_FIELDS = [
    "crown_noun",          # 头饰核心名词：wisteria flower crown -> flower crown
    "crown_back_phrase",   # 段7 后视图："，the back of the flower crown"；无头饰时为空串
    "crown_share_phrase",  # 段8 表情板："，one flower crown"；无头饰时为空串
    "accessories_clause",  # 段5 穿戴列举："，a X crown, Y earrings and Z"；缺项自动重连
    "pron_subj",           # 主格：she / he / they
    "pron_subj_cap",       # 主格句首大写：She / He / They
    "pron_poss",           # 所有格：her / his / their
    "pron_poss_cap",       # 所有格句首大写：Her / His / Their
    "pron_obj",            # 宾格：her / him / them（自定义文案里可用 {o} 引用）
    "pron_cn",             # 中文代词：她 / 他 / TA（自定义文案里可用 {T} 引用）
]

# ---------------- 性别 → 代词 / 人物总称 / 年龄从句主语（只改 gender 一个入口）
PRONOUNS = {
    "female":  {"s": "she",  "S": "She",  "p": "her",   "P": "Her",   "o": "her",  "T": "她"},
    "male":    {"s": "he",   "S": "He",   "p": "his",   "P": "His",   "o": "him",  "T": "他"},
    "neutral": {"s": "they", "S": "They", "p": "their", "P": "Their", "o": "them", "T": "TA"},
}
SUBJECT_NOUNS = {
    "female":  ("a young Chinese fantasy immortal woman", "this woman"),
    "male":    ("a young Chinese fantasy immortal man", "this man"),
    "neutral": ("a young Chinese fantasy immortal figure", "this figure"),
}
AGE_HEADS = {
    "female": "a slender young woman",
    "male": "a slender young man",
    "neutral": "a slender young figure",
}

# 动词第三人称单数：{V:base} 写法 —— female/male 取 -s 形，neutral（they）取原形
VERB_IRREGULAR = {
    "be": ("is", "are"), "have": ("has", "have"), "do": ("does", "do"),
    "go": ("goes", "go"), "watch": ("watches", "watch"), "pass": ("passes", "pass"),
    "raise": ("raises", "raise"), "hold": ("holds", "hold"),
}
VERB_TOKEN = re.compile(r"\{V:([A-Za-z]+)\}")


def conjugate(base, plural):
    b = base.lower()
    if b in VERB_IRREGULAR:
        return VERB_IRREGULAR[b][1 if plural else 0]
    if b.endswith(("s", "x", "z", "ch", "sh")):
        third = b + "es"
    elif b.endswith("y") and len(b) > 1 and b[-2] not in "aeiou":
        third = b[:-1] + "ies"
    else:
        third = b + "s"
    return b if plural else third


# 文案里可用的代词简写，渲染前统一替换（模板与自定义字段都适用）
PRON_TOKENS = {"{s}": "pron_subj", "{S}": "pron_subj_cap",
               "{p}": "pron_poss", "{P}": "pron_poss_cap", "{o}": "pron_obj",
               "{T}": "pron_cn"}

# 头饰核心名词的识别词尾，长词优先（先匹配 flower crown，再匹配 crown）
HEADWEAR_NOUNS = [
    "flower crown", "blossom crown", "leaf crown", "flower wreath",
    "headdress", "hair ornament", "headpiece", "coronet",
    "crown", "wreath", "tiara", "circlet", "hairpin", "headband",
    "hair comb", "comb", "pin", "fillet", "helmet",
]

LIST_FIELDS = {
    "expressions": 4,
    "detail_upper": 4,
    "detail_lower": 4,
    "colors": 6,
    "color_verse": 3,
    "profile": 6,
}

# 省略时自动补齐的字段（表情英文描述有固定范式，允许不改）
OPTIONAL_DEFAULTS = {
    # 发型：默认值 = 4 份验收原稿的写法（半盘半散），换成马尾/发髻/双螺直接覆盖
    "hair_style": "half pinned up and half loose",
    "expr_desc_1": "{p} eyelids sit heavy and half lowered with the pupils showing beneath them, and the corners of {p} mouth curve up into a soft lazy smile",
    "expr_desc_2": "{p} head is upright but {p} lids are lowered until {p} gaze rests down and away and {p} eyes are barely open, {p} lips closed and relaxed",
    "expr_desc_3": "{p} head tips a little back, {p} lids sit low and glossy, {p} lips part loosely and colour rises on both cheeks",
    "expr_desc_4": "{p} head turns three-quarters away from the reader and {p} chin lifts, while {p} eyes turn back toward the reader over {p} shoulder",
    "backdrop": "silhouetted mountain ridges and a small tiered Chinese pavilion standing behind the figure",
    "detail_lower": ["袖摆细节", "裙摆细节", "鞋履细节", "材质细节"],
    "couplet": "我本无心，只因你入梦，便留了心。",
    "pavilion": "a small tiered Chinese pavilion",
    # 持械的那只手：默认不指定左右（保持 4 份原稿写法），要右手/左手直接覆盖
    "weapon_hand": "hand",
    # 内衬底色：默认月白（通用底色），想换直接覆盖
    "underrobe_color": "moon-white",
    # 性别：一个入口同时决定代词（she/her ↔ he/his）与人物总称
    "gender": "female",
}

EXPR_DESC_FIELDS = ["expr_desc_1", "expr_desc_2", "expr_desc_3", "expr_desc_4"]

TEMPLATE_KEYS = SCALAR_FIELDS + EXPR_DESC_FIELDS + COMPUTED_FIELDS + list(LIST_FIELDS)

# 写死探针：这些词属于"角色相关"，只允许出现在变量 JSON 里，绝不允许出现在模板骨架中。
# 缘由：这 4 份验收原稿恰好都是花冠角色，抽模板时 "flower crown" 被误当成常量写进了骨架，
# 结果换了角色还照样戴花冠。以后每发现一次同类问题，就往这个清单里加一个词。
FIXATION_WATCH = [
    r"flower crown", r"moon-white", r"half pinned up", r"same hand",
    r"\bshe\b", r"\bher\b", r"\bhers\b", r"\bwoman\b", r"\bman\b", r"\bgirl\b", r"\blady\b",
]

PLACEHOLDER = re.compile(
    r"\{\{([A-Za-z_][A-Za-z0-9_]*)((?:\[\d+\])*)(?:\.([A-Za-z_][A-Za-z0-9_]*))?\}\}"
)

# 长提示词会触发版面级崩坏（多出一格 / 区块标题重名 / 整块画两遍）
LEN_WARN = 13500


# ---------------------------------------------------------------- 工具

def die(msg, code=2):
    print("[FAIL] " + msg, file=sys.stderr)
    sys.exit(code)


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def join_and(items):
    """['a','b','c'] -> 'a, b and c'；自动跳过空项，永不留下断句的 and。"""
    items = [str(x).strip() for x in items if str(x).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def derive_crown_noun(crown):
    """从完整头饰名里取出核心名词：'wisteria flower crown' -> 'flower crown'。
    返回 (名词, 是否命中已知头饰词尾)；没命中时退化为取最后一个词。"""
    raw = str(crown or "").strip().rstrip(".,;")
    if not raw:
        return "", True
    low = raw.lower()
    for noun in HEADWEAR_NOUNS:          # 已按"长的优先"排序
        if low.endswith(noun):
            return raw[-len(noun):], True
    return raw.split()[-1], False


def apply_pron_tokens(val, out):
    """把 {s} / {p} / {P} 这类简写换成实际代词，{V:base} 换成变位动词；递归处理数组与对象。"""
    if isinstance(val, str):
        plural = out.get("gender") == "neutral"
        if "{V:" in val:
            val = VERB_TOKEN.sub(lambda m: conjugate(m.group(1), plural), val)
        for tok, field in PRON_TOKENS.items():
            if tok in val:
                val = val.replace(tok, str(out.get(field, "")))
        return val
    if isinstance(val, list):
        return [apply_pron_tokens(x, out) for x in val]
    if isinstance(val, dict):
        return {k: apply_pron_tokens(v, out) for k, v in val.items()}
    return val


def fill_defaults(data):
    out = dict(data)

    # ---- 性别：一个入口同时决定代词 / 人物总称 / 年龄从句主语 ----
    g_raw = str(out.get("gender", "") or "").strip().lower()
    gender = g_raw if g_raw in PRONOUNS else "female"
    out["gender"] = gender
    pr = PRONOUNS[gender]
    out["pron_subj"], out["pron_subj_cap"] = pr["s"], pr["S"]
    out["pron_poss"], out["pron_poss_cap"] = pr["p"], pr["P"]
    out["pron_obj"] = pr["o"]
    out["pron_cn"] = pr["T"]
    d_noun, d_ref = SUBJECT_NOUNS[gender]
    if not str(out.get("subject_desc", "") or "").strip():
        out["subject_desc"] = d_noun
    if not str(out.get("subject_ref", "") or "").strip():
        out["subject_ref"] = d_ref
    out["_gender_unknown"] = bool(g_raw) and g_raw not in PRONOUNS

    for key, val in OPTIONAL_DEFAULTS.items():
        if key not in out or out[key] in (None, "", []):
            out[key] = list(val) if isinstance(val, list) else val
    # age_phrase = 年龄从句全句。省略时按默认逗号同位语形式自动拼（主语随性别）
    if not str(out.get("age_phrase", "")).strip() and str(out.get("age_desc", "")).strip():
        out["age_phrase"] = AGE_HEADS[gender] + ", " + str(out["age_desc"]).strip()
    else:
        # 显式写了 age_phrase 也要跟性别对齐：把已知主语换成当前性别的主语
        ap = str(out.get("age_phrase", ""))
        for g2, head in AGE_HEADS.items():
            if g2 != gender and ap.startswith(head):
                out["age_phrase"] = AGE_HEADS[gender] + ap[len(head):]
                break

    # ---- 头饰相关：全部由 crown 派生，crown 留空则整块从句自动消失 ----
    crown = str(out.get("crown", "") or "").strip()
    crown_noun, recognized = derive_crown_noun(crown)
    out["crown_noun"] = crown_noun
    out["crown_back_phrase"] = (", the back of the " + crown_noun) if crown_noun else ""
    out["crown_share_phrase"] = (", one " + crown_noun) if crown_noun else ""
    out["accessories_clause"] = (
        ", " + join_and([("a " + crown) if crown else "",
                         out.get("earrings", ""), out.get("ankle", "")])
    ) if any(str(out.get(k, "") or "").strip() for k in ("crown", "earrings", "ankle")) else ""
    out["_crown_noun_recognized"] = recognized

    # ---- 代词简写替换（放在最后，让所有已算出的字段都能被引用）----
    for k in list(out):
        if not k.startswith("_"):
            out[k] = apply_pron_tokens(out[k], out)
    return out


def resolve(data, name, index, attr):
    if name not in data:
        return None
    val = data[name]
    if index:
        for part in re.findall(r"\[(\d+)\]", index):
            i = int(part)
            if not isinstance(val, list) or i >= len(val):
                return None
            val = val[i]
    if attr:
        if not isinstance(val, dict) or attr not in val:
            return None
        val = val[attr]
    return val


# ---------------------------------------------------------------- 校验

def validate(data, template_text):
    errs, warns = [], []

    # 写死探针：角色相关词一旦被当常量写进骨架，这里直接拦下
    for lit in FIXATION_WATCH:
        m = re.search(lit, template_text, re.IGNORECASE)
        if m:
            errs.append("模板骨架里写死了 %r —— 角色相关词或代词必须走变量，不能当常量。"
                        "（修法见 §6.6：占位符 + 派生字段 + 探针）" % m.group(0))

    for key in SCALAR_FIELDS:
        fname = key[:-2] if re.search(r"_[1-6]$", key) and key.rsplit("_", 1)[0] in LIST_FIELDS else key
        if fname in LIST_FIELDS or key in OMITTABLE_FIELDS:
            continue
        if key not in data or not str(data.get(key, "")).strip():
            errs.append("缺少必填字段：" + key)

    for key, n in LIST_FIELDS.items():
        val = data.get(key)
        if not isinstance(val, list):
            errs.append("字段 %s 必须是数组" % key)
        elif len(val) != n:
            errs.append("字段 %s 必须是 %d 项，当前 %d 项" % (key, n, len(val)))

    for i in range(1, 5):
        if not str(data.get("expr_desc_%d" % i, "")).strip():
            errs.append("缺少必填字段：expr_desc_%d" % i)
    if len(set(str(data.get("expr_desc_%d" % i, "")) for i in range(1, 5))) != 4:
        errs.append("expr_desc_1..4 四条表情描述必须互不相同")

    exps = data.get("expressions") or []
    if len(set(exps)) != len(exps):
        errs.append("expressions 四个表情名必须互不相同")

    det = (data.get("detail_upper") or []) + (data.get("detail_lower") or [])
    if len(set(det)) != len(det):
        errs.append("八个细节图注必须互不相同")

    for cell in det:
        if any(ch in cell for ch in "剑刀枪棍戟") and "细节" not in cell:
            warns.append("图注 %r 里带武器字又不含「细节」，容易被模型字面化成兵器拍出来（实测："
                         "「玉冠剑簪」2/3 次被画成一把剑）。建议改成饰物名" % cell)

    colors = data.get("colors") or []
    for i, c in enumerate(colors):
        if not isinstance(c, dict):
            errs.append("colors[%d] 必须是对象 {hex, cn, en}" % i)
            continue
        for k in ("hex", "cn", "en"):
            if not str(c.get(k, "")).strip():
                errs.append("colors[%d].%s 不能为空" % (i, k))
        if not re.match(r"^#[0-9A-Fa-f]{6}$", str(c.get("hex", ""))):
            errs.append("colors[%d].hex 必须是 #RRGGBB，当前 %r" % (i, c.get("hex")))

    # 模板里出现的占位符必须都能解析到
    for m in PLACEHOLDER.finditer(template_text):
        name, index, attr = m.group(1), m.group(2) or "", m.group(3) or ""
        if name not in TEMPLATE_KEYS:
            warns.append("模板占位符 {{%s}} 不在字段契约里" % m.group(0).strip("{}"))
        elif resolve(data, name, index, attr) is None:
            errs.append("模板需要 %s，但 JSON 里取不到值" % m.group(0))

    # 取值卫生检查
    for key, val in data.items():
        if key in ("preset_id", "theme_label_cn"):
            continue
        for s in ([val] if isinstance(val, str) else
                  [x for x in val if isinstance(x, str)] if isinstance(val, list) else []):
            if "{{" in s or "}}" in s:
                errs.append("字段 %s 的值里不能包含 {{ }}" % key)
            if "'" in s:
                warns.append("字段 %s 的值含单引号，提示词里请统一用双引号" % key)

    if str(data.get("weapon_noun", "")).strip() and len(str(data["weapon_noun"]).split()) > 1:
        warns.append("weapon_noun 建议用单个名词（flute / sword / fan / umbrella），不要带修饰语")

    # 值层面的一致性：模板已被探针管住，这里管用户 / 预设自己填的文案
    _wrong = {
        "female": r"\b(?:he|him|his|man|men|boy|lady\b|他)\b",
        "male": r"\b(?:she|her|hers|woman|women|girl|她)\b",
        "neutral": r"\b(?:she|her|hers|he|him|his|woman|man|girl|boy|她|他)\b",
    }.get(data.get("gender", "female"))
    if _wrong:
        _leftover = set()
        def _scan(v):
            if isinstance(v, str):
                for mm in re.finditer(_wrong, v, re.IGNORECASE):
                    _leftover.add(mm.group(0))
            elif isinstance(v, list):
                for x in v:
                    _scan(x)
            elif isinstance(v, dict):
                for x in v.values():
                    _scan(x)
        for k, v in data.items():
            if not k.startswith("_"):
                _scan(v)
        if _leftover:
            warns.append("gender=%s，但文案里还残留 %s —— 这些词不会被自动替换，"
                         "请改成代词简写：{s} 主格 / {p} 所有格 / {o} 宾格 / {T} 中文代词"
                         % (data.get("gender"), "、".join(sorted(_leftover))))

    if data.get("_gender_unknown"):
        warns.append("gender=%r 不是 female / male / neutral，已按 female 处理" % data.get("gender"))

    # 头饰/饰物留空的提示与派生失败提示
    if all(not str(data.get(k, "") or "").strip() for k in OMITTABLE_FIELDS):
        warns.append("crown / earrings / ankle 三项全空：这位人物将没有头饰、耳饰和踝饰，请确认是有意为之")
    if str(data.get("crown", "") or "").strip() and not data.get("_crown_noun_recognized", True):
        warns.append("crown=%r 没有以已知头饰名词收尾，后视图与表情板里只取了「%s」。"
                     "建议写成「… flower crown / … hairpin / … circlet」这种以头饰名词收尾的形式，"
                     "侧后视图和表情板才指得准" % (data.get("crown"), data.get("crown_noun", "")))

    return errs, warns


# ---------------------------------------------------------------- 渲染

def render(data, template_text):
    missing = []

    def sub(m):
        name, index, attr = m.group(1), m.group(2) or "", m.group(3) or ""
        val = resolve(data, name, index, attr)
        if val is None:
            missing.append(m.group(0))
            return m.group(0)
        return str(val)

    text = PLACEHOLDER.sub(sub, template_text)
    # 模板骨架里也可能出现 {V:base} 这类单花括号令牌，这里统一收口
    text = apply_pron_tokens(text, data)
    if missing:
        die("这些占位符取不到值：%s" % ", ".join(sorted(set(missing))))
    if "{{" in text or "}}" in text:
        die("渲染后仍残留 {{ }}，请检查模板与 JSON")
    _left = re.findall(r"\{V:[^}]*\}|\{[A-Za-z][A-Za-z0-9_]*\}", text)
    if _left:
        die("渲染后仍残留令牌 %s —— 只认这几写法：{s} {S} {p} {P} {o} {T} 与 {V:原形}"
            "（如 {V:hold}）。请检查是不是拼错了" % "、".join(sorted(set(_left))))
    return "\n".join(line.rstrip() for line in text.strip().split("\n"))


def to_single_line(text):
    return text.replace("\n", "\\n")


# ---------------------------------------------------------------- 入口

def build_template_json():
    data = {k: "" for k in SCALAR_FIELDS}
    data["expressions"] = ["", "", "", ""]
    data["detail_upper"] = ["发饰细节", "", "腰饰细节", ""]
    data["detail_lower"] = ["袖摆细节", "裙摆细节", "鞋履细节", "材质细节"]
    data["colors"] = [{"hex": "", "cn": "", "en": ""} for _ in range(6)]
    data["color_verse"] = ["", "我为你，", ""]
    data["profile"] = ["姓名：", "身份：", "年龄：", "性格：", "喜好：", "武器："]
    for i in range(1, 5):
        data["expr_desc_%d" % i] = OPTIONAL_DEFAULTS["expr_desc_%d" % i]
    data["backdrop"] = OPTIONAL_DEFAULTS["backdrop"]
    data["couplet"] = OPTIONAL_DEFAULTS["couplet"]
    # 有默认值的项，prefill 出来方便照着改
    for k in ("underrobe_color", "gender", "hair_style", "weapon_hand"):
        data[k] = OPTIONAL_DEFAULTS[k]
    # 人物总称 / 指代留空即可 —— 渲染时按 gender 自动派生
    data["subject_desc"] = ""
    data["subject_ref"] = ""
    # 这三项可以整项留空：留空 = 这个人物不戴头饰 / 耳饰 / 踝饰，相关从句会自动消失
    for k in OMITTABLE_FIELDS:
        data[k] = ""
    data["preset_id"] = "new_character"
    data["theme_label_cn"] = ""
    return data


def main():
    ap = argparse.ArgumentParser(add_help=True, description="qwen-image-multi-role 提示词渲染器")
    ap.add_argument("--json", help="角色变量 JSON 路径")
    ap.add_argument("--preset", help="内置预设 id：zhiyan / feifeng / heyan / taoyao")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE, help="模板路径（默认 references/template-en.txt）")
    ap.add_argument("--out", help="把提示词写到文件（UTF-8）")
    ap.add_argument("--escape", action="store_true", help="输出单行版：换行写成字面 \\n")
    ap.add_argument("--check", action="store_true", help="只做体检，不输出提示词")
    ap.add_argument("--init", action="store_true", help="打印一份空白变量模板 JSON")
    ap.add_argument("--list-presets", action="store_true", help="列出内置预设")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if args.list_presets:
        if os.path.isdir(PRESET_DIR):
            for f in sorted(os.listdir(PRESET_DIR)):
                if f.endswith(".json"):
                    d = load_json(os.path.join(PRESET_DIR, f))
                    print("%-10s %s" % (os.path.splitext(f)[0], d.get("theme_label_cn", "")))
        return

    if args.init:
        print(json.dumps(build_template_json(), ensure_ascii=False, indent=2))
        return

    if args.preset:
        path = os.path.join(PRESET_DIR, args.preset + ".json")
        if not os.path.isfile(path):
            die("找不到预设 %s（可用：%s）" % (args.preset, ", ".join(
                os.path.splitext(f)[0] for f in os.listdir(PRESET_DIR) if f.endswith(".json"))))
    elif args.json:
        path = args.json
        if not os.path.isfile(path):
            die("找不到 JSON 文件：%s" % path)
    else:
        ap.error("必须给 --json 或 --preset（或用 --init 生成空白模板）")

    data = fill_defaults(load_json(path))
    if not os.path.isfile(args.template):
        die("找不到模板：%s" % args.template)
    with open(args.template, "r", encoding="utf-8") as fh:
        template_text = fh.read()

    errs, warns = validate(data, template_text)

    for w in warns:
        print("[WARN] " + w, file=sys.stderr)
    if errs:
        for e in errs:
            print("[FAIL] " + e, file=sys.stderr)
        die("体检未通过：%d 处错误（提示词未输出）" % len(errs))

    if args.check:
        print("[OK] 体检通过：%d 个字段全部就位，模板占位符全部可解析。" % len(TEMPLATE_KEYS), file=sys.stderr)
        return

    text = render(data, template_text)
    paras = text.count("\n") + 1
    chars = len(text)
    print("[OK] %d 段 / %d 字符" % (paras, chars), file=sys.stderr)
    if chars > LEN_WARN:
        print("[WARN] 提示词 %d 字符，已越过 13500 的稳定门槛：模型更容易画出「多出一格 / 区块标题重名 / "
              "整块被画两遍」。请先删冗余，再加新句子。" % chars, file=sys.stderr)

    payload = to_single_line(text) if args.escape else text
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
        print("[OK] 已写出：%s" % os.path.abspath(args.out), file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
