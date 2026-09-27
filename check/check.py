#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moneysplit 的固定验收程序。**别改这个文件。**

用法：
    bash scripts/check.sh                 跑全部 10 个场景
    bash scripts/check.sh -list           列出全部场景
    bash scripts/check.sh --only kill     只跑一组（kill / hygiene / discriminate / scale）
    bash scripts/check.sh --only kill,scale

输出：逐场景 ``PASS <组>/<名>`` 或 ``FAIL <组>/<名>  期望=… 实际=…``；
      结尾 ``结果：通过 x/N``；全过 exit 0，否则 exit 1。失败不早退，一次把问题全暴露。

场景分组（10 个）：
    kill         3 —— 杀伤率 ≥ 0.95 / 用例在未变异实现上全绿 / 超时变异体按被杀计且报告一致
    hygiene      3 —— 用例不读源码与字节码 / 不 import `_` 前缀私有符号 / 不依赖 time 与 random
    discriminate 2 —— 成对语义近邻各有区分性输入 / 区分性输入落在公开 API 上
    scale        2 —— 用例数 ≥ 40 / 单次全量变异检查 ≤ 90 秒（按本机标定，跑题机慢按比例放宽）

前提：本题要求「用例数 ≥ 40」且「杀伤率 ≥ 0.95」。两条没同时满足时，提交的用例集还算不上
一个有效解，除两条基线场景（kill/unmutated_green、hygiene/no_source_read）外，其余场景
一律判 FAIL，并在「期望」里写明未满足的前提 —— 先把主项做出来，再看其它维度。

只依赖标准库与 python3。
"""

import argparse
import ast
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import mutcheck  # noqa: E402  （固定件之间共享位点表与算子定义）

try:  # 让 UTF-8 报告在任何 locale 下都稳定
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:  # pragma: no cover
    pass

THRESHOLD = mutcheck.THRESHOLD
MIN_TESTS = 40
MAX_SECONDS = 90.0
TEST_DIR = "tests"
PACKAGE_DIR = "moneysplit"

# 成对语义近邻：每个角色至少要有一个位点被用例集杀掉。
PAIR_ROLES = (
    ("rounding_half_up", "round_half_up 与 round_half_even 在半值上的区分"),
    ("allocate_bound", "split 与 allocate 的上限边界"),
    ("percent_sum", "split_by_percent 的 100 与 1 两种写法"),
    ("settle_accum", "settle 的跨笔守恒与单笔守恒"),
    ("negative_sign", "负总额的符号"),
)

SCENARIO_KEYS = (
    "kill/score",
    "kill/unmutated_green",
    "kill/timeout_accounting",
    "hygiene/no_source_read",
    "hygiene/no_private_symbol",
    "hygiene/no_time_random",
    "discriminate/pairs",
    "discriminate/public_api",
    "scale/test_count",
    "scale/runtime",
)
SCENARIO_WHY = (
    "变异检查杀伤率 ≥ %.2f" % THRESHOLD,
    "用例在未变异的实现上全绿（不许靠让实现失败来「杀」变异体）",
    "超时变异体按被杀计，且报告的被杀数与位点数一致",
    "用例不读源码与字节码（open/inspect/dis/hashlib/__file__ 等）",
    "用例只 import moneysplit 包根导出的公开名字，不碰 `_` 前缀私有符号",
    "用例不依赖 time 与 random（无 sleep / 随机 / 墙钟）",
    "成对语义近邻（取整模式 / 上限边界 / 百分比写法 / 跨笔守恒 / 负号）各有区分性输入",
    "区分性输入落在公开 API 上（位点所在函数从公开入口可达）",
    "用例数 ≥ %d" % MIN_TESTS,
    "单次全量变异检查 ≤ %g 秒（按本机标定，跑题机慢按比例放宽）" % MAX_SECONDS,
)

GATE_EXPECT = ("用例集已达规模与杀伤率要求（用例数≥%d、杀伤率≥%.2f）"
               % (MIN_TESTS, THRESHOLD))


# ---------------------------------------------------------------------------
# 事实收集（各算一次，供多个场景复用；结果确定性）
# ---------------------------------------------------------------------------

def _run(command, cwd, timeout=600.0):
    try:
        done = subprocess.run(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT（超过 %g 秒）" % timeout
    return done.returncode, done.stdout.decode("utf-8", "replace")


class Facts(object):
    def __init__(self):
        self._mutcheck = None
        self._scan = None
        self._unmutated = None

    # --- 变异检查一次 ---
    def mutcheck(self):
        if self._mutcheck is None:
            code, out = _run([sys.executable, "mutcheck.py", "--score-min", "0",
                              "--report-sites"], ROOT)
            summary = {}
            sites = {}
            for line in out.splitlines():
                if line.startswith("SUMMARY "):
                    for token in line.split()[1:]:
                        if "=" in token:
                            key, value = token.split("=", 1)
                            summary[key] = value
                elif line.startswith("SITE "):
                    parts = line.split()
                    if len(parts) >= 3 and parts[1].isdigit():
                        sites[int(parts[1])] = parts[2]
            self._mutcheck = (code, out, summary, sites)
        return self._mutcheck

    def summary(self):
        return self.mutcheck()[2]

    def site_status(self):
        return self.mutcheck()[3]

    def mutcheck_raw(self):
        return self.mutcheck()[1]

    def summary_float(self, key):
        try:
            return float(self.summary().get(key, "nan"))
        except ValueError:
            return float("nan")

    # --- tests/ 静态扫描一次 ---
    def scan(self):
        if self._scan is None:
            self._scan = _scan_tests()
        return self._scan

    # --- 未变异实现上跑一次用例 ---
    def unmutated(self):
        if self._unmutated is None:
            self._unmutated = _run(
                [sys.executable, "-B", "-m", "unittest", "discover", "-s", TEST_DIR],
                ROOT)
        return self._unmutated

    # --- 门槛 ---
    def test_count(self):
        return self.scan().get("test_count", 0)

    def gate_ok(self):
        count = self.test_count()
        score = self.summary_float("score")
        return count >= MIN_TESTS and score >= THRESHOLD

    def gate_reason(self):
        return ("用例数=%d（要求≥%d）、杀伤率=%.3f（要求≥%.2f）"
                % (self.test_count(), MIN_TESTS,
                   self.summary_float("score"), THRESHOLD))


FACTS = Facts()


# ---------------------------------------------------------------------------
# tests/ 的静态扫描
# ---------------------------------------------------------------------------

SOURCE_PATTERNS = (
    (re.compile(r"\bopen\s*\("), "open("),
    (re.compile(r"\binspect\b"), "inspect"),
    (re.compile(r"\bdis\b"), "dis"),
    (re.compile(r"\bhashlib\b"), "hashlib"),
    (re.compile(r"__file__"), "__file__"),
    (re.compile(r"\bgetsource\b"), "getsource"),
    (re.compile(r"\bmarshal\b"), "marshal"),
    (re.compile(r"\bimportlib\b"), "importlib"),
    (re.compile(r"__code__"), "__code__"),
    (re.compile(r"\bco_consts\b"), "co_consts"),
    (re.compile(r"\beval\s*\("), "eval("),
    (re.compile(r"\bexec\s*\("), "exec("),
    (re.compile(r"\bcompile\s*\("), "compile("),
    (re.compile(r"\bread_text\b"), "read_text"),
    (re.compile(r"\bread_bytes\b"), "read_bytes"),
)
BAD_MODULES = {"time", "random", "secrets"}
BAD_NAMES = {"sleep", "perf_counter", "monotonic", "process_time", "time_ns",
             "randint", "randrange", "choice", "choices", "shuffle", "sample",
             "seed", "urandom", "getrandbits"}


def _collect_tests():
    base = os.path.join(ROOT, TEST_DIR)
    found = []
    for directory, dirs, names in os.walk(base):
        dirs[:] = sorted(name for name in dirs if name != "__pycache__")
        for name in sorted(names):
            if name.endswith(".py"):
                found.append(os.path.join(directory, name).replace("\\", "/"))
    found.sort()
    return found


def _read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _scan_tests():
    files = _collect_tests()
    texts = {path: _read(path) for path in files}
    trees = {}
    for path, text in texts.items():
        try:
            trees[path] = ast.parse(text, filename=path)
        except SyntaxError:
            trees[path] = None

    total_tests = 0
    for tree in trees.values():
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test"):
                    total_tests += 1

    return {
        "files": files,
        "test_count": total_tests,
        "no_source_read": _check_source_read(texts),
        "no_private_symbol": _check_private_symbol(texts, trees),
        "no_time_random": _check_time_random(texts, trees),
    }


def _check_source_read(texts):
    problems = []
    for path in sorted(texts):
        for lineno, line in enumerate(texts[path].splitlines(), 1):
            for pattern, token in SOURCE_PATTERNS:
                if pattern.search(line):
                    problems.append("%s:%d 用了 %s" % (path, lineno, token))
                    break
    return problems


def _root_name(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _check_private_symbol(texts, trees):
    problems = []
    for path in sorted(trees):
        tree = trees[path]
        if tree is None:
            continue
        bound = {"moneysplit"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                segments = module.split(".")
                if any(seg.startswith("_") for seg in segments):
                    problems.append("%s:%d from %s import ..." % (path, node.lineno, module))
                for alias in node.names:
                    if alias.name != "*" and alias.name.startswith("_"):
                        problems.append("%s:%d from %s import %s"
                                        % (path, node.lineno, module, alias.name))
                    if segments and segments[0] == "moneysplit":
                        bound.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    segments = alias.name.split(".")
                    if any(seg.startswith("_") for seg in segments):
                        problems.append("%s:%d import %s" % (path, node.lineno, alias.name))
                    if segments and segments[0] == "moneysplit":
                        bound.add(alias.asname or alias.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                attr = node.attr
                if attr.startswith("_") and not attr.startswith("__"):
                    if _root_name(node) in bound:
                        problems.append("%s:%d 访问私有符号 .%s" % (path, node.lineno, attr))
    return problems


def _check_time_random(texts, trees):
    problems = []
    for path in sorted(trees):
        tree = trees[path]
        if tree is None:
            continue
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                if module in BAD_MODULES:
                    problems.append("%s:%d from %s import ..." % (path, node.lineno, module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in BAD_MODULES:
                        problems.append("%s:%d import %s" % (path, node.lineno, alias.name))
                    aliases[alias.asname or top] = top
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in BAD_NAMES:
                problems.append("%s:%d 用了 %s" % (path, node.lineno, node.id))
            elif isinstance(node, ast.Attribute):
                if aliases.get(_root_name(node)) in BAD_MODULES:
                    problems.append("%s:%d 用了 %s.%s"
                                    % (path, node.lineno, _root_name(node), node.attr))
    return problems


# ---------------------------------------------------------------------------
# 公开 API 可达性
# ---------------------------------------------------------------------------

def _public_names():
    path = os.path.join(ROOT, PACKAGE_DIR, "__init__.py")
    tree = ast.parse(_read(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    try:
                        names |= {item for item in ast.literal_eval(node.value)}
                    except (ValueError, SyntaxError):
                        pass
    return names


def _package_functions():
    """返回 {函数名: 它直接调用到的本包函数名集合}。"""
    base = os.path.join(ROOT, PACKAGE_DIR)
    graph = {}
    for name in sorted(os.listdir(base)):
        if not name.endswith(".py"):
            continue
        tree = ast.parse(_read(os.path.join(base, name)))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            callees = graph.setdefault(node.name, set())
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
                    callees.add(inner.func.id)
    return graph


def _reachable_from_public():
    graph = _package_functions()
    seen = set()
    pending = list(_public_names())
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        pending.extend(graph.get(name, ()))
    return seen


# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------

def sc_kill_score():
    score = FACTS.summary_float("score")
    if score >= THRESHOLD:
        return True, "杀伤率 ≥ %.2f" % THRESHOLD, "杀伤率 %.3f" % score
    return (False, "杀伤率 ≥ %.2f" % THRESHOLD,
            "杀伤率 %.3f（被杀 %s / 位点 %s）"
            % (score, FACTS.summary().get("killed", "?"),
               FACTS.summary().get("sites", "?")))


def sc_kill_unmutated_green():
    code, out = FACTS.unmutated()
    if code == 0:
        return True, "未变异实现上用例全绿（退出码 0）", "退出码 0"
    tail = " ".join(line for line in out.splitlines()
                    if line.startswith(("FAILED", "ERROR", "Ran "))).strip()
    return False, "未变异实现上用例全绿（退出码 0）", "退出码 %s；%s" % (code, tail[:200])


def sc_kill_timeout_accounting():
    if not FACTS.gate_ok():
        return False, GATE_EXPECT, FACTS.gate_reason()
    code, out = _run([sys.executable, "mutcheck.py", "--score-min", "0",
                      "--timeout", "0.000001"], ROOT)
    summary = {}
    for line in out.splitlines():
        if line.startswith("SUMMARY "):
            for token in line.split()[1:]:
                if "=" in token:
                    key, value = token.split("=", 1)
                    summary[key] = value
    sites = summary.get("sites", "?")
    killed = summary.get("killed", "?")
    survived = summary.get("survived", "?")
    try:
        ok = (int(survived) == 0 and float(summary.get("score", "0")) >= 1.0
              and killed == sites and int(sites) > 0)
    except ValueError:
        ok = False
    if ok:
        return True, "极短超时下存活 0、杀伤率 1.000、被杀数=位点数", \
            "存活 0、被杀 %s/%s" % (killed, sites)
    return (False, "极短超时下存活 0、杀伤率 1.000、被杀数=位点数",
            "存活 %s、杀伤率 %s、被杀 %s / 位点 %s"
            % (survived, summary.get("score", "?"), killed, sites))


def sc_hygiene_no_source_read():
    problems = FACTS.scan()["no_source_read"]
    if not problems:
        return True, "用例不读源码/字节码（无 open/inspect/dis/hashlib/__file__）", "OK"
    return (False, "用例不读源码/字节码（无 open/inspect/dis/hashlib/__file__）",
            "、".join(problems[:3]) + ("、…（共 %d 处）" % len(problems)
                                       if len(problems) > 3 else ""))


def sc_hygiene_no_private_symbol():
    if not FACTS.gate_ok():
        return False, GATE_EXPECT, FACTS.gate_reason()
    problems = FACTS.scan()["no_private_symbol"]
    if not problems:
        return True, "只用 moneysplit 包根导出的公开名字", "OK"
    return (False, "只用 moneysplit 包根导出的公开名字",
            "、".join(problems[:3]) + ("、…（共 %d 处）" % len(problems)
                                       if len(problems) > 3 else ""))


def sc_hygiene_no_time_random():
    if not FACTS.gate_ok():
        return False, GATE_EXPECT, FACTS.gate_reason()
    problems = FACTS.scan()["no_time_random"]
    if not problems:
        return True, "用例不依赖 time 与 random", "OK"
    return (False, "用例不依赖 time 与 random",
            "、".join(problems[:3]) + ("、…（共 %d 处）" % len(problems)
                                       if len(problems) > 3 else ""))


def _role_sites():
    roles = {}
    for index, descriptor in enumerate(mutcheck.SITES):
        role = descriptor[5]
        if role and role != "-":
            roles.setdefault(role, []).append(index)
    return roles


def _pair_problems():
    roles = _role_sites()
    status = FACTS.site_status()
    problems = []
    for role, why in PAIR_ROLES:
        indexes = roles.get(role)
        if not indexes:
            problems.append("%s（%s）在位点表里没有对应位点" % (role, why))
            continue
        alive = [index for index in indexes if status.get(index) != "killed"]
        if alive:
            problems.append("%s（%s）的位点 %s 没被用例杀掉"
                            % (role, why, "、".join(map(str, alive))))
    return problems


def sc_discriminate_pairs():
    problems = _pair_problems()
    if not problems:
        return True, "成对语义近邻各有区分性输入", "5 对全部有区分性输入"
    return False, "成对语义近邻各有区分性输入", "；".join(problems[:4])


def sc_discriminate_public_api():
    problems = _pair_problems()
    if problems:
        return (False, "区分性输入落在公开 API 上（位点所在函数从公开入口可达）",
                "前置未满足：%s" % "；".join(problems[:2]))
    reachable = _reachable_from_public()
    roles = _role_sites()
    bad = []
    for role, _why in PAIR_ROLES:
        for index in roles.get(role, []):
            path, lineno = mutcheck.SITES[index][0], mutcheck.SITES[index][1]
            func = mutcheck.enclosing_function(path, lineno)
            if func is None or func not in reachable:
                bad.append("%s 的区分性位点落在 %s，公开 API 观察不到" % (role, func))
    if bad:
        return (False, "区分性输入落在公开 API 上（位点所在函数从公开入口可达）",
                "；".join(bad[:3]))
    return (True, "区分性输入落在公开 API 上（位点所在函数从公开入口可达）",
            "5 对区分性位点均可从包根入口到达")


def sc_scale_test_count():
    count = FACTS.test_count()
    if count >= MIN_TESTS:
        return True, "用例数 ≥ %d" % MIN_TESTS, "用例数 %d" % count
    return False, "用例数 ≥ %d" % MIN_TESTS, "用例数 %d" % count


def sc_scale_runtime():
    if not FACTS.gate_ok():
        return False, GATE_EXPECT, FACTS.gate_reason()
    elapsed = FACTS.summary_float("elapsed")
    if elapsed <= MAX_SECONDS:
        return True, "全量变异检查 ≤ %g 秒" % MAX_SECONDS, "用时 %.1f 秒" % elapsed
    return (False, "全量变异检查 ≤ %g 秒（按本机标定，跑题机慢按比例放宽）" % MAX_SECONDS,
            "用时 %.1f 秒" % elapsed)


SCENARIOS = {
    "kill/score": sc_kill_score,
    "kill/unmutated_green": sc_kill_unmutated_green,
    "kill/timeout_accounting": sc_kill_timeout_accounting,
    "hygiene/no_source_read": sc_hygiene_no_source_read,
    "hygiene/no_private_symbol": sc_hygiene_no_private_symbol,
    "hygiene/no_time_random": sc_hygiene_no_time_random,
    "discriminate/pairs": sc_discriminate_pairs,
    "discriminate/public_api": sc_discriminate_public_api,
    "scale/test_count": sc_scale_test_count,
    "scale/runtime": sc_scale_runtime,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description="moneysplit 固定验收")
    parser.add_argument("-list", "--list", action="store_true", dest="list_only")
    parser.add_argument("--only", default="")
    args = parser.parse_args(argv)

    if args.list_only:
        for index, key in enumerate(SCENARIO_KEYS):
            print("[%-12s] %-28s %s" % (key.split("/")[0], key, SCENARIO_WHY[index]))
        return 0

    selected = []
    only = [item.strip() for item in args.only.split(",") if item.strip()]
    for key in SCENARIO_KEYS:
        if only and key.split("/")[0] not in only:
            continue
        selected.append(key)
    if not selected:
        print("没有匹配的场景", file=sys.stderr)
        return 2

    passed = 0
    failed = 0
    for key in selected:
        try:
            ok, expected, actual = SCENARIOS[key]()
        except Exception as exc:  # 单场景异常不许拖垮整轮
            ok, expected, actual = False, "场景正常执行", "异常：%s: %s" % (type(exc).__name__, exc)
        if ok:
            passed += 1
            print("PASS %s" % key)
        else:
            failed += 1
            print("FAIL %s  期望=%s 实际=%s" % (key, expected, actual))

    print("结果：通过 %d/%d" % (passed, len(selected)))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
