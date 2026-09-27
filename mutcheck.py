#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moneysplit 的变异测试入口。**这是固定验收程序，不要改它。**

对 ``moneysplit/`` 下的实现做 AST 级「单点变异」：每次只改一处运算或常量，
把改过的源码放进临时工作区，跑一遍 ``tests/`` 里的用例。用例红了说明这个变异体
被「杀掉」；用例还是绿的说明它是「存活变异体」，也就是用例没管住的地方。

变异算子集（只在这些算子上找位点）：

- ``Compare`` 运算符互换（``<`` ↔ ``<=``、``>`` ↔ ``>=``、``==`` ↔ ``!=``、
  ``in`` ↔ ``not in`` …，含边界 ``<=`` ↔ ``<``）
- ``BinOp`` / ``AugAssign`` 运算符互换（``+`` ↔ ``-``、``*`` ↔ ``//``）
- 常量替换（``int`` 加一、``bool`` 取反）
- 内建 ``max`` ↔ ``min`` 互换
- ``sorted`` 的 ``reverse=`` 翻转

**位点表写死在下面的 ``SITES`` 里。** 每个位点都在标定阶段做过穷举差分验证
（``--verify-sites``），确认它会改变实现语义；真正的等价位点（怎么改行为都不变、
任何用例都杀不掉）已经被剔除或替换，保证分母里没有杀不掉的位点。

用法：
    python3 mutcheck.py                      # 跑全部位点，打印杀伤率
    python3 mutcheck.py --score-min 0.95     # 低于该杀伤率时退出码 1
    python3 mutcheck.py --list               # 只列出位点表，不跑用例
    python3 mutcheck.py --jobs 8             # 并行度（默认取 CPU 核数）
    python3 mutcheck.py --timeout 5          # 单个变异体超时（秒）；超时按被杀计
    python3 mutcheck.py --report-sites       # 额外逐位点打印 killed/survived
    python3 mutcheck.py --verify-sites       # 穷举差分验证位点是否真的改变了语义
    python3 mutcheck.py --enumerate          # 列出全部候选位点（标定用）

只依赖标准库。
"""

import argparse
import ast
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGETS = (
    "moneysplit/split.py",
    "moneysplit/rounding.py",
    "moneysplit/ledger.py",
    "moneysplit/errors.py",
    "moneysplit/__init__.py",
)
TEST_DIR = "tests"
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}
THRESHOLD = 0.95

try:  # 让 UTF-8 报告在任何 locale 下都稳定（固定件要能被脚本解析）
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:  # pragma: no cover - 老解释器没有 reconfigure
    pass

CMP_SWAP = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
}
BIN_SWAP = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.FloorDiv,
    ast.FloorDiv: ast.Mult,
}
CALL_SWAP = {"max": "min", "min": "max"}

# ---------------------------------------------------------------------------
# 位点表：写死。每项是 (相对路径, 行号, 算子, 变异说明, 同行同型位点的序号, 角色)
#
# 「角色」是给固定件判别用的语义标签，普通位点写 "-"；
#   rounding_half_up  半值朝 +∞ 取整 / half_even 的区分
#   allocate_bound    容量上限边界
#   percent_sum       百分比之和 100 / 1 两种写法
#   settle_accum      settle 的单笔守恒与跨笔累加
#   negative_sign     负总额的符号
# ---------------------------------------------------------------------------
SITES = [
    # --- split.py：分摊主干 ---
    ("moneysplit/split.py", 31, "constant", "1->2", 0, "-"),
    ("moneysplit/split.py", 32, "call", "max->min", 0, "negative_sign"),
    ("moneysplit/split.py", 42, "compare", "Eq->NotEq", 0, "-"),
    ("moneysplit/split.py", 45, "sort", "reverse=off->on", 0, "-"),
    ("moneysplit/split.py", 59, "compare", "NotEq->Eq", 0, "-"),
    ("moneysplit/split.py", 60, "binop", "Mult->FloorDiv", 0, "-"),
    ("moneysplit/split.py", 61, "binop", "FloorDiv->Mult", 0, "-"),
    ("moneysplit/split.py", 64, "binop", "Sub->Add", 0, "-"),
    ("moneysplit/split.py", 67, "augassign", "Add->Sub", 0, "-"),
    ("moneysplit/split.py", 67, "constant", "1->2", 0, "-"),
    ("moneysplit/split.py", 89, "binop", "Mult->FloorDiv", 0, "-"),
    ("moneysplit/split.py", 99, "augassign", "Add->Sub", 0, "-"),
    ("moneysplit/split.py", 112, "constant", "100->101", 0, "percent_sum"),
    # --- split.py：空权重 / 百分比写法 / 上限边界 ---
    ("moneysplit/split.py", 42, "constant", "0->1", 0, "-"),
    ("moneysplit/split.py", 65, "sort", "reverse=off->on", 0, "-"),
    ("moneysplit/split.py", 84, "compare", "NotEq->Eq", 0, "-"),
    ("moneysplit/split.py", 112, "constant", "1->2", 0, "percent_sum"),
    ("moneysplit/split.py", 118, "compare", "NotEq->Eq", 0, "-"),
    ("moneysplit/split.py", 119, "augassign", "Add->Sub", 0, "-"),
    ("moneysplit/split.py", 133, "compare", "Gt->GtE", 0, "allocate_bound"),
    ("moneysplit/split.py", 134, "binop", "Sub->Add", 0, "-"),
    # --- rounding.py：四种取整模式 ---
    ("moneysplit/rounding.py", 24, "binop", "FloorDiv->Mult", 0, "-"),
    ("moneysplit/rounding.py", 30, "binop", "FloorDiv->Mult", 0, "-"),
    ("moneysplit/rounding.py", 36, "binop", "FloorDiv->Mult", 0, "-"),
    ("moneysplit/rounding.py", 36, "binop", "Add->Sub", 0, "rounding_half_up"),
    ("moneysplit/rounding.py", 36, "binop", "Mult->FloorDiv", 0, "-"),
    ("moneysplit/rounding.py", 42, "binop", "FloorDiv->Mult", 0, "-"),
    ("moneysplit/rounding.py", 43, "binop", "Sub->Add", 0, "-"),
    ("moneysplit/rounding.py", 44, "binop", "Mult->FloorDiv", 0, "-"),
    ("moneysplit/rounding.py", 45, "compare", "Lt->LtE", 0, "-"),
    ("moneysplit/rounding.py", 47, "compare", "Gt->GtE", 0, "-"),
    ("moneysplit/rounding.py", 49, "compare", "Eq->NotEq", 0, "-"),
    # --- ledger.py：跨笔结算 net 累加与 journal ---
    ("moneysplit/ledger.py", 33, "compare", "Eq->NotEq", 0, "-"),
    ("moneysplit/ledger.py", 33, "constant", "0->1", 0, "-"),
    ("moneysplit/ledger.py", 34, "compare", "NotEq->Eq", 0, "-"),
    ("moneysplit/ledger.py", 34, "constant", "0->1", 0, "-"),
    ("moneysplit/ledger.py", 37, "binop", "Mult->FloorDiv", 0, "-"),
    ("moneysplit/ledger.py", 37, "constant", "0->1", 0, "-"),
    ("moneysplit/ledger.py", 43, "augassign", "Add->Sub", 0, "settle_accum"),
    ("moneysplit/ledger.py", 43, "binop", "Mult->FloorDiv", 0, "-"),
]


class _Candidate(object):
    """一个候选位点。"""

    __slots__ = ("kind", "label", "lineno", "col", "node")

    def __init__(self, kind, label, node):
        self.kind = kind
        self.label = label
        self.lineno = getattr(node, "lineno", 0)
        self.col = getattr(node, "col_offset", 0)
        self.node = node


def _swap_label(kind, old, new):
    return "%s->%s" % (old, new)


def _sorted_candidates(tree):
    """按 (行号, 列号) 列出全部候选位点，顺序确定。"""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = node.ops[0]
            if type(op) in CMP_SWAP:
                found.append(_Candidate(
                    "compare",
                    _swap_label("compare", type(op).__name__,
                                CMP_SWAP[type(op)].__name__),
                    node,
                ))
        elif isinstance(node, ast.BinOp) and type(node.op) in BIN_SWAP:
            found.append(_Candidate(
                "binop",
                _swap_label("binop", type(node.op).__name__,
                            BIN_SWAP[type(node.op)].__name__),
                node,
            ))
        elif isinstance(node, ast.AugAssign) and type(node.op) in BIN_SWAP:
            found.append(_Candidate(
                "augassign",
                _swap_label("augassign", type(node.op).__name__,
                            BIN_SWAP[type(node.op)].__name__),
                node,
            ))
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                label = "%s->%s" % (node.value, not node.value)
            elif isinstance(node.value, int):
                label = "%d->%d" % (node.value, node.value + 1)
            else:
                continue
            found.append(_Candidate("constant", label, node))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name in CALL_SWAP:
                found.append(_Candidate("call", "%s->%s" % (name, CALL_SWAP[name]), node))
            elif name == "sorted":
                present = [kw for kw in node.keywords if kw.arg == "reverse"]
                if not present:
                    label = "reverse=off->on"
                elif (isinstance(present[0].value, ast.Constant)
                      and isinstance(present[0].value.value, bool)):
                    label = "reverse=%s->%s" % (
                        present[0].value.value, not present[0].value.value)
                else:
                    label = "reverse=?->True"
                found.append(_Candidate("sort", label, node))
    found.sort(key=lambda item: (item.lineno, item.col))
    return found


def _apply(node, kind):
    """就地把一个位点改成变异后的形式。"""
    if kind == "compare":
        node.ops[0] = CMP_SWAP[type(node.ops[0])]()
    elif kind in ("binop", "augassign"):
        node.op = BIN_SWAP[type(node.op)]()
    elif kind == "constant":
        if isinstance(node.value, bool):
            node.value = not node.value
        else:
            node.value = node.value + 1
    elif kind == "call":
        node.func.id = CALL_SWAP[node.func.id]
    elif kind == "sort":
        for keyword in node.keywords:
            if keyword.arg == "reverse":
                if (isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, bool)):
                    keyword.value.value = not keyword.value.value
                else:
                    keyword.value = ast.Constant(value=True)
                break
        else:
            node.keywords.append(
                ast.keyword(arg="reverse", value=ast.Constant(value=True)))
    else:  # pragma: no cover - 位点表写错时才会走到
        raise ValueError("未知算子：%s" % kind)


def _find_node(tree, lineno, kind, label, nth):
    """按 (行号, 算子, 说明) 定位位点；同型同行的第 nth 个。"""
    matches = [item for item in _sorted_candidates(tree)
               if item.lineno == lineno and item.kind == kind and item.label == label]
    if len(matches) <= nth:
        return None
    return matches[nth].node


def _mutated_source(source, descriptor):
    """返回改过该位点后的源码；位点不存在或改不动时返回 None。"""
    _path, lineno, kind, label, nth, _role = descriptor
    tree = ast.parse(source)
    node = _find_node(tree, lineno, kind, label, nth)
    if node is None:
        return None
    _apply(node, kind)
    ast.fix_missing_locations(tree)
    try:
        text = ast.unparse(tree)
        ast.parse(text)
    except (SyntaxError, ValueError):  # pragma: no cover
        return None
    if text == source:
        return None
    return text


def _read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


def _load_sources():
    return {path: _read(path) for path in TARGETS}


def _enumerate_all():
    """列出所有目标文件里的候选位点，附加所属函数名与源码行。"""
    rows = []
    for path in TARGETS:
        source = _read(path)
        lines = source.splitlines()
        full = ast.parse(source)
        for item in _sorted_candidates(full):
            text = lines[item.lineno - 1].strip() if item.lineno - 1 < len(lines) else ""
            rows.append({
                "path": path,
                "lineno": item.lineno,
                "col": item.col,
                "kind": item.kind,
                "label": item.label,
                "scope": enclosing_function(path, item.lineno) or "<module>",
                "text": text,
            })
    return rows


def enclosing_function(path, lineno):
    """返回 ``path`` 里 ``lineno`` 所在函数的名字（最内层）；找不到返回 None。"""
    tree = ast.parse(_read(path))
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= lineno <= getattr(node, "end_lineno", node.lineno):
                if best is None or node.lineno > best[0]:
                    best = (node.lineno, node.name)
    return best[1] if best is not None else None


# ---------------------------------------------------------------------------
# 跑用例 / 评估变异体
# ---------------------------------------------------------------------------

def _prepare_workspace(workspace):
    if os.path.isdir(workspace):
        shutil.rmtree(workspace, ignore_errors=True)
    shutil.copytree(ROOT, workspace, ignore=shutil.ignore_patterns(*SKIP_DIRS))


def _run_tests(workspace, timeout):
    command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", TEST_DIR]
    try:
        done = subprocess.run(
            command,
            cwd=workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return True, "timeout"
    if done.returncode != 0:
        return True, "fail"
    return False, "pass"


def _drop_caches(workspace):
    for base, dirs, _files in os.walk(workspace):
        for name in list(dirs):
            if name == "__pycache__":
                shutil.rmtree(os.path.join(base, name), ignore_errors=True)
                dirs.remove(name)


def _restore_all(workspace, sources):
    """把**全部**目标文件还原（不是只还原刚改过的那个）。"""
    for original, source in sources.items():
        with open(os.path.join(workspace, original), "w", encoding="utf-8") as handle:
            handle.write(source)


def _evaluate(sites, sources, index, workspace, timeout):
    descriptor = sites[index]
    path = descriptor[0]
    text = _mutated_source(sources[path], descriptor)
    if text is None:
        return None
    _drop_caches(workspace)
    with open(os.path.join(workspace, path), "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    try:
        killed, reason = _run_tests(workspace, timeout)
    finally:
        _restore_all(workspace, sources)
    return {"index": index, "path": path, "descriptor": descriptor,
            "killed": killed, "reason": reason}


def _evaluate_all(sites, sources, args):
    results = {}
    skipped = []
    temp_root = tempfile.mkdtemp(prefix="mutcheck-")
    try:
        workers = max(1, min(args.jobs, len(sites) or 1))
        workspaces = []
        for worker in range(workers):
            workspace = os.path.join(temp_root, "worker%d" % worker)
            _prepare_workspace(workspace)
            workspaces.append(workspace)

        lock = threading.Lock()

        def run_worker(worker):
            workspace = workspaces[worker]
            batch = list(range(worker, len(sites), workers))
            for index in batch:
                outcome = _evaluate(sites, sources, index, workspace, args.timeout)
                with lock:
                    if outcome is None:
                        skipped.append(index)
                    else:
                        results[index] = outcome

        threads = [threading.Thread(target=run_worker, args=(worker,))
                   for worker in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    return [results[index] for index in sorted(results)], skipped


def _descriptor_text(descriptor):
    path, lineno, kind, label, _nth, role = descriptor
    role_text = "" if role in ("-", None) else " [%s]" % role
    return "%s:%d %s %s%s" % (path, lineno, kind, label, role_text)


def _print_summary(sites, results, skipped, elapsed, report_sites):
    total = len(results)
    killed = [item for item in results if item["killed"]]
    survived = [item for item in results if not item["killed"]]
    score = (len(killed) / total) if total else 0.0
    print("杀伤率 %.3f（%d 个位点杀 %d 个，阈值 %.2f）"
          % (score, total, len(killed), THRESHOLD))
    print("位点表 %d 个 · 无法定位 %d 个 · 用时 %.1fs"
          % (len(sites), len(skipped), elapsed))
    print("SUMMARY sites=%d skipped=%d killed=%d survived=%d score=%.6f "
          "elapsed=%.3f threshold=%.2f"
          % (len(sites), len(skipped), len(killed), len(survived), score,
             elapsed, THRESHOLD))
    if report_sites:
        for item in results:
            print("SITE %d %s %s"
                  % (item["index"], "killed" if item["killed"] else "survived",
                     _descriptor_text(item["descriptor"])))
    if survived:
        print("存活变异体（这些地方用例没管住）：")
        for item in survived:
            print("  #%-4d %s（%s）"
                  % (item["index"], _descriptor_text(item["descriptor"]), item["reason"]))
    if skipped:
        print("无法定位的位点（位点表与实现不一致）：%s" % ", ".join(map(str, skipped)))
    return score


# ---------------------------------------------------------------------------
# 穷举差分验证：位点是否真的改变了语义
# ---------------------------------------------------------------------------

_PROBE_SOURCE = r'''# -*- coding: utf-8 -*-
"""确定性探针：把公开 API 的行为打成一份可比较的记录。"""
from fractions import Fraction

from moneysplit import (InsufficientCapacity, allocate, merge, round_ceil,
                        round_floor, round_half_even, round_half_up, settle,
                        split, split_by_percent)


def show(label, action):
    try:
        value = action()
    except Exception as exc:
        print("%s !! %s: %s" % (label, type(exc).__name__, exc))
    else:
        print("%s => %r" % (label, value))


WEIGHTS = ([], [1], [0], [1, 1], [1, 2], [2, 1], [3, 1], [1, 1, 1],
           [0, 0], [0, 1], [1, 0], [3, 0, 1], [5, 3, 2], [1, 1, 1, 1], [7, 2, 1])
TOTALS = [-103, -7, -3, -1, 0, 1, 2, 3, 7, 10, 11, 100, 101, 999]
BAD_WEIGHTS = ([-1, 2], [1, -2], [-1, -1], [1.0, 1], [True, 1], [1, False],
               [2, -0, 1])
TUPLE_WEIGHTS = ((1, 1), (3, 1, 1))
BAD_ENTRIES = ([1.5], [True], [False, 2], [1, -1.0])
PERCENTS = ([100], [50, 50], [1], [30, 30, 40], [0, 100], [100, 0], [1, 0],
            [0, 1], [33, 33, 34], [1, 1, 1])
PERCENTS_TINY = ([1, 99], [99, 1], [1, 1, 98], [50, 1, 49], [1, 1], [-1, 101])
FRACTIONS = [Fraction(0), Fraction(1), Fraction(-1), Fraction(1, 2),
             Fraction(3, 2), Fraction(5, 2), Fraction(7, 2), Fraction(-1, 2),
             Fraction(-3, 2), Fraction(1, 3), Fraction(2, 3), Fraction(7, 3),
             Fraction(-7, 3), Fraction(5, 4), Fraction(9, 4), Fraction(-5, 4)]

for total in TOTALS:
    for weights in WEIGHTS:
        show("split(%d,%r)" % (total, weights), lambda t=total, w=weights: split(t, w))
        show("merge(split(%d,%r))" % (total, weights),
             lambda t=total, w=weights: merge(split(t, w)))
        show("settle([%d],%r)" % (total, weights),
             lambda t=total, w=weights: settle([t], w))
        show("settle([1,%d],%r)" % (total, weights),
             lambda t=total, w=weights: settle([1, t], w))
        show("settle([%d,-1,2],%r)" % (total, weights),
             lambda t=total, w=weights: settle([t, -1, 2], w))
        show("allocate(%d,%r)" % (total, weights),
             lambda t=total, w=weights: allocate(t, w))
    for weights in BAD_WEIGHTS:
        show("split(%d,%r) bad-weights" % (total, weights),
             lambda t=total, w=weights: split(t, w))
        show("allocate(%d,%r) bad-weights" % (total, weights),
             lambda t=total, w=weights: allocate(t, w))
        show("settle([1,%d],%r) bad-weights" % (total, weights),
             lambda t=total, w=weights: settle([1, t], w))
        show("split_by_percent(%d,%r) bad-percents" % (total, weights),
             lambda t=total, w=weights: split_by_percent(t, w))
    for weights in TUPLE_WEIGHTS:
        show("split(%d,%r) tuple" % (total, weights),
             lambda t=total, w=weights: split(t, w))
        show("settle([%d],%r) tuple" % (total, weights),
             lambda t=total, w=weights: settle([t], w))
    for entries in BAD_ENTRIES:
        show("settle(%r,[1,2]) bad-entries" % (entries,),
             lambda e=entries: settle(e, [1, 2]))

for total in TOTALS:
    for percents in PERCENTS + PERCENTS_TINY:
        show("split_by_percent(%d,%r)" % (total, percents),
             lambda t=total, p=percents: split_by_percent(t, p))

for value in FRACTIONS:
    for name, func in (("floor", round_floor), ("ceil", round_ceil),
                       ("half_up", round_half_up), ("half_even", round_half_even)):
        show("%s(%r)" % (name, value), lambda f=func, v=value: f(v))

show("settle([],[])", lambda: settle([], []))
show("settle([], [1,1])", lambda: settle([], [1, 1]))
show("settle([0,0],[0,0])", lambda: settle([0, 0], [0, 0]))
show("merge([])", lambda: merge([]))
show("merge([1,-1,2])", lambda: merge([1, -1, 2]))
show("split(0,[])", lambda: split(0, []))
show("allocate(0,[])", lambda: allocate(0, []))
show("split(1.5,[1,1])", lambda: split(1.5, [1, 1]))
show("split(True,[1,1])", lambda: split(True, [1, 1]))
show("split(1,[True,1])", lambda: split(1, [True, 1]))
show("merge([True])", lambda: merge([True]))
show("split(-1,[1,1])", lambda: split(-1, [1, 1]))
show("settle([True],[1,1])", lambda: settle([True], [1, 1]))
show("split_by_percent(10,[1,1])", lambda: split_by_percent(10, [1, 1]))
show("split_by_percent(10,[100])", lambda: split_by_percent(10, [100]))
show("split_by_percent(10,[0])", lambda: split_by_percent(10, [0]))
show("split(10,[0,0])", lambda: split(10, [0, 0]))
show("split(7,[1,2])", lambda: split(7, [1, 2]))
show("split(10,[3,0,1])", lambda: split(10, [3, 0, 1]))
show("allocate(5,[5])", lambda: allocate(5, [5]))
show("allocate(6,[5])", lambda: allocate(6, [5]))
show("settle([7,7],[1,2])", lambda: settle([7, 7], [1, 2]))
show("settle([-7,3],[1,2])", lambda: settle([-7, 3], [1, 2]))
show("settle([5,-5],[1,1,1])", lambda: settle([5, -5], [1, 1, 1]))
'''


def _probe_transcript(workspace, timeout):
    """在工作区里跑一次探针，返回输出的字符串。"""
    probe = os.path.join(workspace, "_probe.py")
    with open(probe, "w", encoding="utf-8") as handle:
        handle.write(_PROBE_SOURCE)
    try:
        done = subprocess.run(
            [sys.executable, "-B", probe],
            cwd=workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    return done.stdout.decode("utf-8", "replace")


def verify_sites(args):
    """穷举差分：每个位点在探针语料上的行为是否与原始实现不同。"""
    sources = _load_sources()
    sites = SITES
    started = time.time()
    temp_root = tempfile.mkdtemp(prefix="mutverify-")
    try:
        baseline = os.path.join(temp_root, "baseline")
        shutil.copytree(ROOT, baseline, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        reference = _probe_transcript(baseline, args.probe_timeout)

        workers = max(1, min(args.jobs, len(sites) or 1))
        workspaces = []
        for worker in range(workers):
            workspace = os.path.join(temp_root, "v%d" % worker)
            shutil.copytree(ROOT, workspace, ignore=shutil.ignore_patterns(*SKIP_DIRS))
            workspaces.append(workspace)

        lock = threading.Lock()
        verdicts = {}

        def run_worker(worker):
            workspace = workspaces[worker]
            batch = list(range(worker, len(sites), workers))
            for index in batch:
                descriptor = sites[index]
                path = descriptor[0]
                text = _mutated_source(sources[path], descriptor)
                if text is None:
                    with lock:
                        verdicts[index] = (False, "位点无法定位/未产生变化")
                    continue
                with open(os.path.join(workspace, path), "w", encoding="utf-8") as handle:
                    handle.write(text + "\n")
                try:
                    transcript = _probe_transcript(workspace, args.probe_timeout)
                finally:
                    _restore_all(workspace, sources)
                if transcript == "TIMEOUT":
                    with lock:
                        verdicts[index] = (True, "探针超时（行为已不同）")
                elif transcript == reference:
                    with lock:
                        verdicts[index] = (False, "疑似等价位点：探针语料上行为完全一致")
                else:
                    with lock:
                        verdicts[index] = (True, "语义已变化")

        threads = [threading.Thread(target=run_worker, args=(worker,))
                   for worker in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    changed = 0
    equivalent = []
    for index, descriptor in enumerate(sites):
        ok, why = verdicts.get(index, (False, "未评估"))
        if ok:
            changed += 1
        else:
            equivalent.append(index)
        print("%s #%-3d %s — %s"
              % ("OK   " if ok else "EQUIV", index, _descriptor_text(descriptor), why))
    print("位点表 %d 个 · 语义已变化 %d 个 · 疑似等价 %d 个 · 用时 %.1fs"
          % (len(sites), changed, len(equivalent), time.time() - started))
    if equivalent:
        print("疑似等价位点名次：%s" % ", ".join(map(str, equivalent)))
        print("这些位点必须从分母里剔除或替换，否则阈值 %.2f 不可达。" % THRESHOLD)
        return 1
    return 0


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="moneysplit 变异测试入口")
    parser.add_argument("--score-min", type=float, default=THRESHOLD)
    parser.add_argument("--list", action="store_true", dest="list_only")
    parser.add_argument("--jobs", type=int, default=max(1, os.cpu_count() or 1))
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--probe-timeout", type=float, default=15.0)
    parser.add_argument("--report-sites", action="store_true")
    parser.add_argument("--verify-sites", action="store_true")
    parser.add_argument("--enumerate", action="store_true")
    args = parser.parse_args(argv)

    if args.enumerate:
        rows = _enumerate_all()
        for index, row in enumerate(rows):
            print("#%-4d %s:%-4d %-9s %-14s %s | %s"
                  % (index, row["path"], row["lineno"], row["kind"], row["label"],
                     row["scope"], row["text"]))
        print("共 %d 个候选位点" % len(rows))
        return 0

    if args.list_only:
        for index, descriptor in enumerate(SITES):
            print("#%-4d %s" % (index, _descriptor_text(descriptor)))
        print("共 %d 个变异位点" % len(SITES))
        return 0

    if args.verify_sites:
        return verify_sites(args)

    sources = _load_sources()
    started = time.time()
    results, skipped = _evaluate_all(SITES, sources, args)
    elapsed = time.time() - started
    score = _print_summary(SITES, results, skipped, elapsed, args.report_sites)

    if score + 1e-9 < args.score_min:
        print("未达标：杀伤率 %.3f < %.3f" % (score, args.score_min))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
