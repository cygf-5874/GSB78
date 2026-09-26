#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moneysplit 的变异测试入口。**这个文件是固定验收入口，不要改它。**

对 ``moneysplit/`` 下的实现做 AST 级「单点变异」：每次只改一处运算或常量，
把改过的源码放进临时工作区，跑一遍 ``tests/`` 里的用例。
用例红了说明这个变异体被「杀掉」；用例还是绿的说明它是「存活变异体」，
也就是用例没管住的地方。

变异算子（都在 ``moneysplit/split.py``、``moneysplit/rounding.py`` 上找位点）：

- 比较运算符互换（``<`` ↔ ``<=``、``>`` ↔ ``>=``、``==`` ↔ ``!=``、``in`` ↔ ``not in`` …）
- 算术运算符互换（``+`` ↔ ``-``、``*`` ↔ ``//``）
- 布尔运算符互换（``and`` ↔ ``or``）
- 常量替换（``int`` 加一、``bool`` 取反）
- 取反去掉（``not X`` → ``X``）
- 返回值改 ``None``（``return X`` → ``return None``）
- 内建 ``max`` ↔ ``min`` 互换

用法：
    python3 mutcheck.py                     # 跑全部变异体，打印杀伤率
    python3 mutcheck.py --score-min 0.90    # 低于该杀伤率时退出码 1
    python3 mutcheck.py --list              # 只列出变异位点，不跑用例
    python3 mutcheck.py --jobs 4            # 并行度（默认取 CPU 核数）
    python3 mutcheck.py --timeout 5         # 单个变异体超时（秒）；超时按被杀计
    python3 mutcheck.py --max-survivors 20  # 最多打印多少个存活变异体

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
    os.path.join("moneysplit", "split.py"),
    os.path.join("moneysplit", "rounding.py"),
    os.path.join("moneysplit", "errors.py"),
)
TEST_DIR = "tests"
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}

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


class _Mutator(ast.NodeTransformer):
    """按确定顺序遍历语法树；既能枚举位点，也能改第 N 个位点。"""

    def __init__(self, mode, target=None):
        self.mode = mode
        self.target = target
        self.hits = 0
        self.sites = []
        self.applied = None

    def _consider(self, node, kind, label, maker):
        if self.mode == "list":
            self.sites.append((kind, getattr(node, "lineno", 0), label))
            return node
        if self.hits == self.target:
            self.hits += 1
            self.applied = (kind, getattr(node, "lineno", 0), label)
            return maker(node)
        self.hits += 1
        return node

    def visit_Compare(self, node):
        if len(node.ops) == 1 and type(node.ops[0]) in CMP_SWAP:
            old = type(node.ops[0]).__name__
            new = CMP_SWAP[type(node.ops[0])].__name__
            result = self._consider(
                node, "compare", "%s->%s" % (old, new), self._swap_compare
            )
            if result is not node:
                return result
        return self.generic_visit(node)

    def _swap_compare(self, node):
        node.ops[0] = CMP_SWAP[type(node.ops[0])]()
        return ast.fix_missing_locations(node)

    def visit_BoolOp(self, node):
        swap = ast.Or if isinstance(node.op, ast.And) else ast.And
        result = self._consider(
            node,
            "boolop",
            "%s->%s" % (type(node.op).__name__, swap.__name__),
            self._swap_boolop,
        )
        if result is not node:
            return result
        return self.generic_visit(node)

    def _swap_boolop(self, node):
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        return ast.fix_missing_locations(node)

    def visit_BinOp(self, node):
        if type(node.op) in BIN_SWAP:
            label = "%s->%s" % (type(node.op).__name__, BIN_SWAP[type(node.op)].__name__)
            result = self._consider(node, "binop", label, self._swap_binop)
            if result is not node:
                return result
        return self.generic_visit(node)

    def _swap_binop(self, node):
        node.op = BIN_SWAP[type(node.op)]()
        return ast.fix_missing_locations(node)

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            label = "%s->%s" % (node.value, not node.value)
        elif isinstance(node.value, int):
            label = "%d->%d" % (node.value, node.value + 1)
        else:
            return self.generic_visit(node)
        result = self._consider(node, "constant", label, self._bump_constant)
        if result is not node:
            return result
        return self.generic_visit(node)

    def _bump_constant(self, node):
        if isinstance(node.value, bool):
            node.value = not node.value
        else:
            node.value = node.value + 1
        return node

    def visit_UnaryOp(self, node):
        if isinstance(node.op, ast.Not):
            result = self._consider(node, "unaryop", "not->identity", self._drop_not)
            if result is not node:
                return result
        return self.generic_visit(node)

    def _drop_not(self, node):
        return ast.copy_location(node.operand, node)

    def visit_Return(self, node):
        if node.value is not None and not _is_none_constant(node.value):
            result = self._consider(node, "return", "return->None", self._null_return)
            if result is not node:
                return result
        return self.generic_visit(node)

    def _null_return(self, node):
        node.value = ast.Constant(value=None)
        return ast.fix_missing_locations(node)

    def visit_Call(self, node):
        func = node.func
        if isinstance(func, ast.Name) and func.id in CALL_SWAP:
            label = "%s->%s" % (func.id, CALL_SWAP[func.id])
            result = self._consider(node, "call", label, self._swap_builtin)
            if result is not node:
                return result
        return self.generic_visit(node)

    def _swap_builtin(self, node):
        node.func.id = CALL_SWAP[node.func.id]
        return ast.fix_missing_locations(node)


def _is_none_constant(node):
    return isinstance(node, ast.Constant) and node.value is None


def _mutated_source(source, index):
    """返回改过第 index 个位点之后的源码；位点不存在时返回 (None, None)。"""
    tree = ast.parse(source)
    mutator = _Mutator("apply", target=index)
    tree = mutator.visit(tree)
    if mutator.applied is None:
        return None, None
    ast.fix_missing_locations(tree)
    try:
        text = ast.unparse(tree)
        ast.parse(text)
    except (SyntaxError, ValueError):
        return None, None
    if text == source:
        return None, None
    return text, mutator.applied


def _enumerate_sites(source):
    tree = ast.parse(source)
    mutator = _Mutator("list")
    mutator.visit(tree)
    return mutator.sites


def _load_targets():
    """读出所有目标文件，返回 (源码表, 位点表)。

    位点表里每一项是 ``(相对路径, 类型, 行号, 说明)``，顺序确定。
    """
    sources = {}
    sites = []
    for path in TARGETS:
        with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
            sources[path] = handle.read()
        for site in _enumerate_sites(sources[path]):
            sites.append((path,) + tuple(site))
    return sources, sites


def _local_index(sites, index):
    """把全局位点序号换算成所属文件内部的序号。"""
    path = sites[index][0]
    local = 0
    for earlier in range(index):
        if sites[earlier][0] == path:
            local += 1
    return path, local


def _prepare_workspace(base, workspace):
    if os.path.isdir(workspace):
        shutil.rmtree(workspace, ignore_errors=True)
    shutil.copytree(
        base,
        workspace,
        ignore=shutil.ignore_patterns(*SKIP_DIRS),
    )


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


def _evaluate(args, sources, sites, index, workspace):
    path, local = _local_index(sites, index)
    text, site = _mutated_source(sources[path], local)
    if text is None:
        return None
    _drop_caches(workspace)
    target = os.path.join(workspace, path)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")
    try:
        killed, reason = _run_tests(workspace, args.timeout)
    finally:
        # 工作区是复用的：跑完必须把**所有**目标文件还原，
        # 否则上一位点留在别的文件里的变异会污染下一位点。
        for original, source in sources.items():
            with open(os.path.join(workspace, original), "w", encoding="utf-8") as handle:
                handle.write(source)
    return {"index": index, "path": path, "site": site, "killed": killed, "reason": reason}


def main(argv=None):
    parser = argparse.ArgumentParser(description="moneysplit 变异测试入口")
    parser.add_argument("--score-min", type=float, default=0.90)
    parser.add_argument("--list", action="store_true", dest="list_only")
    parser.add_argument("--jobs", type=int, default=max(1, os.cpu_count() or 1))
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-survivors", type=int, default=20)
    args = parser.parse_args(argv)

    sources, sites = _load_targets()
    if args.list_only:
        for index, (path, kind, lineno, label) in enumerate(sites):
            print("#%-4d %s:%-4d %-9s %s" % (index, path, lineno, kind, label))
        print("共 %d 个变异位点" % len(sites))
        return 0

    started = time.time()
    results = []
    skipped = 0
    temp_root = tempfile.mkdtemp(prefix="mutcheck-")
    try:
        workers = max(1, min(args.jobs, len(sites) or 1))
        workspaces = []
        for worker in range(workers):
            workspace = os.path.join(temp_root, "worker%d" % worker)
            _prepare_workspace(ROOT, workspace)
            workspaces.append(workspace)

        # 每份工作区里只跑自己那一批位点，工作区之间互不影响；
        # 子进程是等待型的，用线程池就能把 --jobs 变成真正的并行度。
        lock = threading.Lock()
        outcomes = {}

        def run_worker(worker):
            workspace = workspaces[worker]
            batch = list(range(worker, len(sites), workers))
            for index in batch:
                outcome = _evaluate(args, sources, sites, index, workspace)
                with lock:
                    outcomes[index] = outcome

        threads = [
            threading.Thread(target=run_worker, args=(worker,))
            for worker in range(workers)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        for index in range(len(sites)):
            outcome = outcomes.get(index)
            if outcome is None:
                skipped += 1
            else:
                results.append(outcome)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    total = len(results)
    killed = [item for item in results if item["killed"]]
    survived = [item for item in results if not item["killed"]]
    score = (len(killed) / total) if total else 0.0

    print("工作区：%s（固定入口，勿改）" % "、".join(TARGETS))
    print(
        "变异位点 %d 个 · 跳过 %d 个 · 存活变异体 %d 个 · 杀伤率 %.3f · 用时 %.1fs"
        % (len(sites), skipped, len(survived), score, time.time() - started)
    )
    # 机器可读汇总：scripts/check.sh 只认这一行（不依赖中文编码）。
    print(
        "SUMMARY sites=%d skipped=%d killed=%d survived=%d score=%.6f elapsed=%.3f"
        % (len(sites), skipped, len(killed), len(survived), score, time.time() - started)
    )
    if survived:
        print("存活变异体（这些地方用例没管住）：")
        for item in survived[: args.max_survivors]:
            kind, lineno, label = item["site"]
            print("  #%-4d %s:%-4d %-9s %s" % (item["index"], item["path"], lineno, kind, label))
        if len(survived) > args.max_survivors:
            print("  … 另外 %d 个" % (len(survived) - args.max_survivors))

    if score + 1e-9 < args.score_min:
        print("未达标：杀伤率 %.3f < %.3f" % (score, args.score_min))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
