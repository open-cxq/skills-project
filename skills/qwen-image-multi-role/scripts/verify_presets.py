#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qwen-image-multi-role / verify_presets.py
=========================================
回归验证：把 scripts/presets/ 里的每一套变量渲染一遍，与 references/examples/ 下
对应的人工验收原稿做逐字符比对（忽略空白差异与手工转义的 \\" ）。

用法：
  python verify_presets.py            # 4/4 全一致才算通过（返回码 0）

用途：任何一次修改 references/template-en.txt 之后都必须跑这个。改坏了立刻能看出来。
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXAMPLES = os.path.join(ROOT, "references", "examples")

PAIRS = [
    ("zhiyan", "紫嫣角色多视图.txt"),
    ("feifeng", "绯枫角色多视图.txt"),
    ("heyan", "禾晏角色多视图.txt"),
    ("taoyao", "桃夭角色多视图.txt"),
]


def norm(s):
    """忽略换行形式、缩进、手工转义引号：只比较实际内容。"""
    s = s.replace("\\n", "").replace('\\"', '"')
    return re.sub(r"\s+", "", s)


# ---------------------------------------------------------- 第 2 关：可变化检查
# 4 份原稿全是一类角色（女性 / 花冠），所以"逐字符一致"只能证明没跑偏，
# 证明不了模板对**别的**角色也对。这一关专门换掉头饰与人物总称，看句子还成不成立。

def variation_checks():
    sys.path.insert(0, HERE)
    import render_prompt as R

    with open(os.path.join(ROOT, "references", "template-en.txt"), "r", encoding="utf-8") as fh:
        tpl = fh.read()

    def render_with(mutate):
        data = R.load_json(os.path.join(R.PRESET_DIR, "zhiyan.json"))
        mutate(data)
        data = R.fill_defaults(data)              # 派生必须发生在改值之后
        errs, _ = R.validate(data, tpl)
        if errs:
            raise AssertionError("这组变量本不该报错，却报了：%s" % "; ".join(errs))
        return R.render(data, tpl)

    cases = []

    def gadget_regions(t):
        """取出三处「饰物」片段单独嗅探空槽残留 —— 全文扫逗号会误伤原稿的自然行文。"""
        out = []
        for a, b in [("long gauze sleeves", " She holds"),
                     ("showing the back of her head", "and the back of the robe"),
                     ("share one face, one hairstyle", "and one framing")]:
            i = t.find(a)
            j = t.find(b, i if i >= 0 else 0)
            if i >= 0 and j >= 0:
                out.append(t[i + len(a):j])
        return out

    BAD_JOIN = [", ,", ",,", " ,", ",.", " .", "  ", ", and and"]

    def no_empty_slot(t):
        return not any(b in r for r in gadget_regions(t) for b in BAD_JOIN)

    # 1) 完全没有头饰 / 耳饰 / 踝饰
    t = render_with(lambda d: [d.pop(k, None) for k in ("crown", "earrings", "ankle")])
    cases += [
        ("无头饰：不再凭空出现花冠", "flower crown" not in t.lower()),
        ("无头饰：后视图从句自动消失", "showing the back of her head and the back of the robe" in t),
        ("无头饰：表情板从句自动消失", "share one face, one hairstyle and one framing" in t),
        ("无头饰：穿戴句收成干净一句",
         "with translucent long gauze sleeves. She holds" in t),
        ("无头饰：饰物片段无空槽", no_empty_slot(t)),
    ]

    # 2) 不是花冠，换成玉凤簪
    t = render_with(lambda d: d.update(crown="jade phoenix hairpin"))
    cases += [
        ("玉凤簪：后视图改称 hairpin", "the back of the hairpin" in t),
        ("玉凤簪：表情板改称 hairpin", "one hairstyle, one hairpin and one framing" in t),
        ("玉凤簪：不再出现 flower crown", "flower crown" not in t.lower()),
        ("玉凤簪：穿戴句三项齐全",
         "long gauze sleeves, a jade phoenix hairpin, butterfly-wing silver earrings "
         "and silver ankle ornaments." in t),
        ("玉凤簪：饰物片段无空槽", no_empty_slot(t)),
    ]

    # 3) 只摘掉耳饰（三项变两项，连接词要重排）
    t = render_with(lambda d: d.pop("earrings", None))
    cases += [
        ("只缺耳饰：连接词重排为 A and B",
         "long gauze sleeves, a wisteria flower crown and silver ankle ornaments." in t),
        ("只缺耳饰：饰物片段无空槽", no_empty_slot(t)),
    ]

    # 4) 男相：只改 gender 一个字段，代词 / 总称 / 年龄从句 / 中文代词应一起换
    t = render_with(lambda d: d.update(gender="male"))
    cases += [
        ("男相：总称自动改为 man", "character card of a young Chinese fantasy immortal man" in t),
        ("男相：指代自动改为 this man", "Every picture of this man on the card" in t),
        ("男相：所有格改为 his", "glancing back over his shoulder" in t),
        ("男相：宾格改为 him", "raised before him" in t),
        ("男相：年龄从句主语改为 man", "a slender young man, likely in his late teens" in t),
        ("男相：表情描述跟随（{p} 令牌）", "his eyelids sit heavy" in t),
        ("男相：中文代词改为 他", "他" in t and "她" not in t),
        ("男相：全文不留 she / her / woman", not re.search(r"\b(?:she|her|hers|woman|girl)\b", t, re.I)),
    ]

    # 5) 中性：they / their
    t = render_with(lambda d: d.update(gender="neutral"))
    cases += [
        ("中性：所有格改为 their", "glancing back over their shoulder" in t),
        ("中性：总称改为 figure", "character card of a young Chinese fantasy immortal figure" in t),
        ("中性：中文代词改为 TA", "TA" in t and "她" not in t),
        ("中性：动词取原形（They hold）", "They hold a white jade" in t),
        ("中性：have 取原形（they have turned）", "they have turned" in t),
        ("中性：wears 取原形（they wear）", "they wear a moon-white" in t),
        ("中性：全文不留 she / her / woman", not re.search(r"\b(?:she|her|hers|woman|girl)\b", t, re.I)),
    ]

    # 6) 特殊身份：手动覆盖人物总称（gender 仍管代词）
    t = render_with(lambda d: d.update(
        gender="female",
        subject_desc="a young Chinese fox-spirit immortal woman",
        subject_ref="this fox spirit"))
    cases += [
        ("身份可自定义", "character card of a young Chinese fox-spirit immortal woman" in t),
        ("指代可自定义", "Every picture of this fox spirit on the card" in t),
    ]

    # 7) 内衬底色可换（默认月白，换成霜蓝）
    t = render_with(lambda d: d.update(underrobe_color="frost blue"))
    cases += [
        ("内衬底色可覆盖", "she wears a frost blue crossed-collar under-robe" in t),
        ("内衬改色后不再残留月白", "moon-white" not in t.lower()),
    ]

    return cases


# ---------------------------------------------------------- 第 3 关：写死探针

def defense_checks():
    """故意破坏，防线必须拦下 —— 证明防线还活着，不是摆设。"""
    sys.path.insert(0, HERE)
    import render_prompt as R
    with open(os.path.join(ROOT, "references", "template-en.txt"), "r", encoding="utf-8") as fh:
        tpl = fh.read()
    raw = R.load_json(os.path.join(R.PRESET_DIR, "zhiyan.json"))
    out = []

    def written_back(marker, replacement):
        dirty = tpl.replace(marker, replacement)
        if dirty == tpl:
            return None
        data = R.fill_defaults(dict(raw))
        errs, _ = R.validate(data, dirty)
        return any("写死" in e for e in errs)

    r1 = written_back("{{crown_share_phrase}}", ", one flower crown")
    out.append((r1 is True, "写死的 flower crown 被拦下" if r1 else "flower crown 写死没被拦下"))

    r2 = written_back("{{pron_poss}} shoulder", "her shoulder")
    out.append((r2 is True, "写死的 her 被拦下" if r2 else "her 写死没被拦下"))

    # 未知令牌：必须硬失败（退出码 2），不能原样漏进提示词
    data = R.fill_defaults(dict(raw))
    data["hold_tail"] = "raised before {q} lips"
    import contextlib as _cl, io as _io
    try:
        with _cl.redirect_stderr(_io.StringIO()):   # 这一条本来就该报错，别让它吓到人
            R.render(data, tpl)
        caught = False
    except SystemExit as e:
        caught = (e.code == 2)
    out.append((caught, "未知令牌 {q} 被拦下" if caught else "未知令牌漏进提示词了"))

    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # ---- 第 1 关：4 份原稿逐字符一致 ----
    ok = True
    for preset, fname in PAIRS:
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "render_prompt.py"), "--preset", preset],
            capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            print("[FAIL] %-9s 渲染失败：%s" % (preset, (proc.stderr or "").strip()[:300]))
            ok = False
            continue
        got = norm(proc.stdout)
        ref_path = os.path.join(EXAMPLES, fname)
        with open(ref_path, "rb") as fh:
            raw = fh.read()
        try:
            ref_text = raw.decode("utf-8")
        except UnicodeDecodeError:
            ref_text = raw.decode("gbk")
        ref = norm(ref_text)
        if got == ref:
            print("[OK]   %-9s 与原稿逐字符一致（%d 字符）" % (preset, len(got)))
        else:
            ok = False
            print("[FAIL] %-9s 与原稿不一致：渲染 %d 字符 / 原稿 %d 字符" % (preset, len(got), len(ref)))
            import difflib
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref, got).get_opcodes():
                if tag != "equal":
                    print("         %s  原稿=%r  渲染=%r" % (tag, ref[i1:i2][:120], got[j1:j2][:120]))
    print()
    if ok:
        print("== 第 1 关 4/4 全部一致 —— 模板没跑偏 ==")
    else:
        print("== 第 1 关：有预设对不上，模板或变量被改坏了，先回滚再改 ==")
        sys.exit(2)

    # ---- 第 2 关：换掉头饰与人物总称，句子还成不成立 ----
    print()
    vok = True
    try:
        for label, passed in variation_checks():
            print("[%s] 换装 %s" % ("OK  " if passed else "FAIL", label))
            vok = vok and passed
    except AssertionError as e:
        print("[FAIL] 换装检查异常：%s" % e)
        vok = False
    print()
    if vok:
        print("== 第 2 关 换装检查全部通过 —— 头饰与人物总称真的可以换 ==")
    else:
        print("== 第 2 关：模板对非花冠角色不成立，说明又写死了东西 ==")

    # ---- 第 3 关：防线自检（故意破坏，必须被拦）----
    print()
    dok = True
    for passed, label in defense_checks():
        print("[%s] 防线 %s" % ("OK  " if passed else "FAIL", label))
        dok = dok and passed
    print()
    if dok:
        print("== 第 3 关 防线自检通过：写死与非法令牌都会被拦 ==")
    else:
        print("== 第 3 关：防线失效 —— 拦不住了，先修防线 ==")

    if vok and dok:
        print()
        print("== 三关全过：原稿未跑偏 / 变量真能换 / 防线拦得住 ==")
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
