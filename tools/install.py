#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 skills/ 下的技能安装（或同步）到智能体的技能目录。

零第三方依赖，只用标准库。

用法：
    python tools/install.py --to <DIR>        # 安装/更新到指定技能目录
    python tools/install.py --check           # 只比对不写入；有差异时退出码 2
    python tools/install.py --skill <NAME>    # 只处理指定技能
    python tools/install.py --prune           # 同时删除目标里已从仓库移除的文件

目标目录通过 --to 指定，或用环境变量 AGENT_SKILLS_DIR 预设。本脚本**不假定**任何
具体智能体的目录位置 —— 不同智能体读取技能的目录不同（用户主目录下的点目录、或项目内
目录等），由使用者按所用智能体的说明决定。

为什么需要它：安装位置是仓库的**副本**（不是符号链接），两边会各自漂移。
改完仓库里的技能后跑一次本脚本，或用 --check 在 CI / 提交前确认没有漂移。
"""

import argparse
import hashlib
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC_ROOT = os.path.join(REPO, "skills")
ENV_VAR = "AGENT_SKILLS_DIR"
DEFAULT_DEST = os.environ.get(ENV_VAR) or None

SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode"}
SKIP_FILES = {".DS_Store", "Thumbs.db", "Desktop.ini"}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(root):
    """返回 {相对路径: (md5, 大小)}。"""
    out = {}
    if not os.path.isdir(root):
        return out
    for cur, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name in SKIP_FILES:
                continue
            full = os.path.join(cur, name)
            rel = os.path.relpath(full, root)
            try:
                out[rel] = (md5(full), os.path.getsize(full))
            except OSError as exc:
                print("  ! 读取失败 %s: %s" % (rel, exc))
    return out


def list_skills():
    if not os.path.isdir(SRC_ROOT):
        return []
    return sorted(
        d for d in os.listdir(SRC_ROOT)
        if os.path.isdir(os.path.join(SRC_ROOT, d))
        and os.path.isfile(os.path.join(SRC_ROOT, d, "SKILL.md"))
    )


def sync_one(name, dest_root, check, prune):
    src = os.path.join(SRC_ROOT, name)
    dst = os.path.join(dest_root, name)
    s, d = scan(src), scan(dst)

    added = sorted(set(s) - set(d))
    removed = sorted(set(d) - set(s))
    changed = sorted(k for k in set(s) & set(d) if s[k][0] != d[k][0])

    print("── %s → %s" % (name, dst))
    if not (added or removed or changed):
        print("   已是最新（%d 个文件）" % len(s))
        return 0

    for k in added:
        print("   + 新增 %s" % k)
    for k in changed:
        print("   ~ 更新 %s  (%d → %d B)" % (k, d[k][1], s[k][1]))
    for k in removed:
        print("   - 目标多余 %s%s" % (k, "" if prune else "  （加 --prune 才会删除）"))

    if check:
        print("   共 %d 处差异（--check 模式，未写入）" % (len(added) + len(changed) + len(removed)))
        return 2

    for k in added + changed:
        target = os.path.join(dst, k)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(src, k), target)
    if prune:
        for k in removed:
            os.remove(os.path.join(dst, k))
    print("   已同步：新增 %d / 更新 %d / 删除 %d" % (
        len(added), len(changed), len(removed) if prune else 0))
    return 0


def main():
    ap = argparse.ArgumentParser(description="安装或同步 skills/ 下的技能到智能体技能目录")
    ap.add_argument("--to", default=DEFAULT_DEST,
                    help="目标技能目录（也可用环境变量 %s 预设）" % ENV_VAR)
    ap.add_argument("--skill", default=None, help="只处理指定技能名")
    ap.add_argument("--check", action="store_true", help="只比对不写入；有差异退出码 2")
    ap.add_argument("--prune", action="store_true", help="删除目标里已从仓库移除的文件")
    args = ap.parse_args()

    if not args.to:
        print("需要指定目标技能目录。", file=sys.stderr)
        print("  方式一：python tools/install.py --to <你的技能目录>", file=sys.stderr)
        print("  方式二：设置环境变量 %s 后直接运行" % ENV_VAR, file=sys.stderr)
        print("说明：技能是纯文本目录，放进你所用的智能体读取技能的目录即可；"
              "本脚本不假定任何具体位置。", file=sys.stderr)
        return 1

    names = list_skills()
    if args.skill:
        if args.skill not in names:
            print("找不到技能 %r；可用：%s" % (args.skill, "、".join(names) or "（无）"))
            return 1
        names = [args.skill]
    if not names:
        print("skills/ 下没有可安装的技能（每个技能目录需含 SKILL.md）")
        return 1

    print("仓库：%s" % SRC_ROOT)
    print("目标：%s" % args.to)
    print()

    rc = 0
    for n in names:
        rc = max(rc, sync_one(n, args.to, args.check, args.prune))

    print()
    if rc == 0:
        print("== 全部一致 ==" if args.check else "== 安装完成 ==")
    else:
        print("== 有差异：安装位置与仓库不一致，跑一次不带 --check 的命令即可对齐 ==")
    return rc


if __name__ == "__main__":
    sys.exit(main())
