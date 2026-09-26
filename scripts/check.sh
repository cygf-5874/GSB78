#!/usr/bin/env bash
# moneysplit 的固定验收程序。**别改这个文件。**
#
# 用法：
#   bash scripts/check.sh                 跑全部 8 个场景
#   bash scripts/check.sh -list           列出全部场景
#   bash scripts/check.sh --only kill     只跑一组（kill / hygiene / scale），可用逗号分隔
#
# 输出：逐场景 `PASS <组>/<名>` 或 `FAIL <组>/<名>  期望=… 实际=…`；
#       结尾 `结果：通过 x/N`；全过 exit 0，否则 exit 1。失败不早退，一次把问题全暴露。
#
# 场景分组（8 个）：
#   kill     3 —— 杀伤率 ≥ 阈值 / 用例在未变异实现上全绿 / 超时变异体按被杀计且报告一致
#   hygiene  3 —— 用例不读源码与字节码 / 不 import `_` 前缀私有符号 / 不依赖 time 与 random
#   scale    2 —— 用例数 ≥ 40 / 单次全量变异检查 ≤ 60 秒（按本机标定，跑题机慢按比例放宽）
#
# 前提：本题要求「用例数 ≥ 40」且「杀伤率 ≥ 0.90」。两条没同时满足时，提交的用例集还算不上
# 一个有效解，除两条基线场景（kill/unmutated_green、hygiene/no_source_read）外，
# 其余场景一律判 FAIL，并在「期望」里写明未满足的前提 —— 先把主项做出来，再看其它维度。
#
# 只依赖标准库与 python3。
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

THRESHOLD=0.90
MIN_TESTS=40
MAX_SECONDS=60.0

PY=python3
if ! command -v python3 >/dev/null 2>&1; then
  PY=python
fi
if ! command -v "$PY" >/dev/null 2>&1; then
  printf '找不到 python3 / python 解释器\n' >&2
  exit 2
fi

GATE_EXPECT="用例集已达规模与杀伤率要求（用例数≥${MIN_TESTS}、杀伤率≥$(printf '%.3f' "$THRESHOLD")）"

SCENARIO_KEYS=(
  kill/score
  kill/unmutated_green
  kill/timeout_accounting
  hygiene/no_source_read
  hygiene/no_private_symbol
  hygiene/no_time_random
  scale/test_count
  scale/runtime
)
SCENARIO_WHY=(
  "变异检查杀伤率 ≥ $(printf '%.3f' "$THRESHOLD")"
  "用例在未变异的实现上全绿（不许靠让实现失败来「杀」变异体）"
  "超时变异体按被杀计，且报告的被杀数与位点数一致"
  "用例不读源码与字节码（open/inspect/dis/hashlib/__file__ 等）"
  "用例不 import \`_\` 前缀私有符号，也不碰 moneysplit 的私有属性"
  "用例不依赖 time 与 random（无 sleep / 随机 / 墙钟）"
  "用例数 ≥ ${MIN_TESTS}"
  "单次全量变异检查 ≤ ${MAX_SECONDS} 秒（按本机标定，跑题机慢按比例放宽）"
)

# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

pass_scenario() { printf 'PASS %s/%s\n' "$1" "$2"; return 0; }

fail_scenario() { printf 'FAIL %s/%s  期望=%s 实际=%s\n' "$1" "$2" "$3" "$4"; return 1; }

ge() { awk -v a="$1" -v b="$2" 'BEGIN{exit !((a+0) >= (b+0))}'; }

le() { awk -v a="$1" -v b="$2" 'BEGIN{exit !((a+0) <= (b+0))}'; }

# mutcheck.py 的一次全量运行（结果缓存，供多个场景复用）
MUTCHECK_RAN=0
MUTCHECK_OUT=""
MUTCHECK_SUMMARY=""

run_mutcheck() {
  if [ "$MUTCHECK_RAN" = "0" ]; then
    MUTCHECK_OUT="$("$PY" mutcheck.py --score-min 0 2>&1)"
    MUTCHECK_SUMMARY="$(printf '%s\n' "$MUTCHECK_OUT" | grep '^SUMMARY ' | tail -n 1)"
    MUTCHECK_RAN=1
  fi
}

mutcheck_field() {
  printf '%s\n' "$MUTCHECK_SUMMARY" | sed -n "s/.* $1=\([^ ]*\).*/\1/p"
}

# tests/ 的静态扫描（结果缓存）
SCAN_RAN=0
SCAN_OUT=""

run_scan() {
  if [ "$SCAN_RAN" = "0" ]; then
    SCAN_OUT="$("$PY" - <<'PY'
import ast
import os
import re

TESTS = os.environ.get("MONEYSPLIT_TESTS", "tests")


def collect():
    found = []
    for base, dirs, names in os.walk(TESTS):
        dirs[:] = sorted(name for name in dirs if name != "__pycache__")
        for name in sorted(names):
            if name.endswith(".py"):
                found.append(os.path.join(base, name).replace("\\", "/"))
    found.sort()
    return found


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


SOURCE_PATTERNS = [
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
]

BAD_MODULES = {"time", "random", "secrets"}
BAD_NAMES = {
    "sleep", "perf_counter", "monotonic", "process_time", "time_ns",
    "randint", "randrange", "choice", "choices", "shuffle", "sample",
    "seed", "urandom", "getrandbits",
}

FILES = collect()
TREES = {}
for _path in FILES:
    try:
        TREES[_path] = ast.parse(read(_path), filename=_path)
    except SyntaxError:
        TREES[_path] = None


def count_tests():
    total = 0
    for tree in TREES.values():
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test"):
                    total += 1
    return total


def check_source_read():
    problems = []
    for path in FILES:
        for lineno, line in enumerate(read(path).splitlines(), 1):
            for pattern, token in SOURCE_PATTERNS:
                if pattern.search(line):
                    problems.append("%s:%d %s" % (path, lineno, token))
                    break
    return problems


def _root_name(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def check_private_symbol():
    problems = []
    for path, tree in TREES.items():
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
                    if alias.name == "*":
                        continue
                    if alias.name.startswith("_"):
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
                        problems.append("%s:%d .%s" % (path, node.lineno, attr))
    return problems


def check_time_random():
    problems = []
    for path, tree in TREES.items():
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
                problems.append("%s:%d %s" % (path, node.lineno, node.id))
            elif isinstance(node, ast.Attribute):
                root = _root_name(node)
                if aliases.get(root) in BAD_MODULES:
                    problems.append("%s:%d %s.%s" % (path, node.lineno, root, node.attr))
    return problems


def report(name, problems):
    if problems:
        shown = "、".join(problems[:3])
        if len(problems) > 3:
            shown += "、…（共 %d 处）" % len(problems)
        print("%s FAIL %s" % (name, shown))
    else:
        print("%s OK" % name)


print("test_count %d" % count_tests())
report("no_source_read", check_source_read())
report("no_private_symbol", check_private_symbol())
report("no_time_random", check_time_random())
PY
)"
    SCAN_RAN=1
  fi
}

scan_field() {
  printf '%s\n' "$SCAN_OUT" | awk -v key="$1" '$1 == key { $1 = ""; sub(/^ /, ""); print; exit }'
}

gate_ok() {
  run_scan
  run_mutcheck
  local count score
  count="$(scan_field test_count)"
  score="$(mutcheck_field score)"
  [ -n "$count" ] && [ -n "$score" ] || return 1
  [ "$count" -ge "$MIN_TESTS" ] || return 1
  ge "$score" "$THRESHOLD"
}

gate_reason() {
  run_scan
  run_mutcheck
  printf '用例数=%s（要求≥%d）、杀伤率=%s（要求≥%s）' \
    "$(scan_field test_count)" "$MIN_TESTS" "$(mutcheck_field score)" \
    "$(printf '%.3f' "$THRESHOLD")"
}

# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------

sc_kill_score() {
  run_mutcheck
  local score sites killed
  score="$(mutcheck_field score)"
  sites="$(mutcheck_field sites)"
  killed="$(mutcheck_field killed)"
  if [ -n "$score" ] && ge "$score" "$THRESHOLD"; then
    pass_scenario kill score
  else
    fail_scenario kill score "杀伤率 ≥ $(printf '%.3f' "$THRESHOLD")" \
      "杀伤率 ${score:-无}（被杀 ${killed:-?} / 位点 ${sites:-?}）"
  fi
}

sc_kill_unmutated_green() {
  local out status
  out="$("$PY" -B -m unittest discover -s tests 2>&1)"
  status=$?
  if [ "$status" = "0" ]; then
    pass_scenario kill unmutated_green
  else
    fail_scenario kill unmutated_green "未变异实现上用例全绿（退出码 0）" \
      "退出码 $status；$(printf '%s' "$out" | grep -E '^(FAILED|ERROR|Ran )' | tail -n 2 | tr '\n' ' ')"
  fi
}

sc_kill_timeout_accounting() {
  if ! gate_ok; then
    fail_scenario kill timeout_accounting "$GATE_EXPECT" "$(gate_reason)"
    return
  fi
  local out sites killed survived score
  out="$("$PY" mutcheck.py --score-min 0 --timeout 0.000001 2>&1)"
  local summary
  summary="$(printf '%s\n' "$out" | grep '^SUMMARY ' | tail -n 1)"
  sites="$(printf '%s\n' "$summary" | sed -n 's/.* sites=\([^ ]*\).*/\1/p')"
  killed="$(printf '%s\n' "$summary" | sed -n 's/.* killed=\([^ ]*\).*/\1/p')"
  survived="$(printf '%s\n' "$summary" | sed -n 's/.* survived=\([^ ]*\).*/\1/p')"
  score="$(printf '%s\n' "$summary" | sed -n 's/.* score=\([^ ]*\).*/\1/p')"
  if [ "$survived" = "0" ] && [ -n "$score" ] && ge "$score" 1.0 && [ "$killed" = "$sites" ]; then
    pass_scenario kill timeout_accounting
  else
    fail_scenario kill timeout_accounting "极短超时下存活 0、杀伤率 1.000、被杀数=位点数" \
      "存活 ${survived:-?}、杀伤率 ${score:-?}、被杀 ${killed:-?} / 位点 ${sites:-?}"
  fi
}

sc_hygiene_no_source_read() {
  run_scan
  local detail
  detail="$(scan_field no_source_read)"
  if [ "$detail" = "OK" ]; then
    pass_scenario hygiene no_source_read
  else
    fail_scenario hygiene no_source_read "用例不读源码/字节码（无 open/inspect/dis/hashlib/__file__）" "$detail"
  fi
}

sc_hygiene_no_private_symbol() {
  run_scan
  if ! gate_ok; then
    fail_scenario hygiene no_private_symbol "$GATE_EXPECT" "$(gate_reason)"
    return
  fi
  local detail
  detail="$(scan_field no_private_symbol)"
  if [ "$detail" = "OK" ]; then
    pass_scenario hygiene no_private_symbol
  else
    fail_scenario hygiene no_private_symbol "只用 moneysplit 包根导出的公开名字" "$detail"
  fi
}

sc_hygiene_no_time_random() {
  run_scan
  if ! gate_ok; then
    fail_scenario hygiene no_time_random "$GATE_EXPECT" "$(gate_reason)"
    return
  fi
  local detail
  detail="$(scan_field no_time_random)"
  if [ "$detail" = "OK" ]; then
    pass_scenario hygiene no_time_random
  else
    fail_scenario hygiene no_time_random "用例不依赖 time 与 random" "$detail"
  fi
}

sc_scale_test_count() {
  run_scan
  local count
  count="$(scan_field test_count)"
  if [ -n "$count" ] && [ "$count" -ge "$MIN_TESTS" ]; then
    pass_scenario scale test_count
  else
    fail_scenario scale test_count "用例数 ≥ $MIN_TESTS" "用例数 ${count:-0}"
  fi
}

sc_scale_runtime() {
  if ! gate_ok; then
    fail_scenario scale runtime "$GATE_EXPECT" "$(gate_reason)"
    return
  fi
  run_mutcheck
  local elapsed
  elapsed="$(mutcheck_field elapsed)"
  if [ -n "$elapsed" ] && le "$elapsed" "$MAX_SECONDS"; then
    pass_scenario scale runtime
  else
    fail_scenario scale runtime "全量变异检查 ≤ ${MAX_SECONDS} 秒（按本机标定，跑题机慢按比例放宽）" \
      "用时 ${elapsed:-?} 秒"
  fi
}

run_scenario() {
  case "$1" in
    kill/score)                 sc_kill_score ;;
    kill/unmutated_green)       sc_kill_unmutated_green ;;
    kill/timeout_accounting)    sc_kill_timeout_accounting ;;
    hygiene/no_source_read)     sc_hygiene_no_source_read ;;
    hygiene/no_private_symbol)  sc_hygiene_no_private_symbol ;;
    hygiene/no_time_random)     sc_hygiene_no_time_random ;;
    scale/test_count)           sc_scale_test_count ;;
    scale/runtime)              sc_scale_runtime ;;
    *)                          return 2 ;;
  esac
}

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

LIST_ONLY=0
ONLY=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -list|--list) LIST_ONLY=1 ;;
    --only|--group)
      shift
      if [ "$#" -eq 0 ]; then
        printf -- '--only 需要一个组名（kill / hygiene / scale）\n' >&2
        exit 2
      fi
      ONLY="$1"
      ;;
    -h|--help)
      printf '用法: bash scripts/check.sh [-list] [--only <组名>]\n'
      exit 0
      ;;
    *)
      printf '未知参数: %s\n' "$1" >&2
      exit 2
      ;;
  esac
  shift
done

if [ "$LIST_ONLY" = "1" ]; then
  index=0
  for key in "${SCENARIO_KEYS[@]}"; do
    printf '[%-9s] %-36s %s\n' "${key%%/*}" "$key" "${SCENARIO_WHY[$index]}"
    index=$((index + 1))
  done
  exit 0
fi

selected_count=0
passed=0
failed=0
index=0

# 先把两个「事实」各算一次（用例扫描 + 一次全量变异检查），后续场景复用，
# 这样 --only 与整体跑的结论一致，也不会把变异检查跑两遍。
run_scan
run_mutcheck

for key in "${SCENARIO_KEYS[@]}"; do
  group="${key%%/*}"
  why="${SCENARIO_WHY[$index]}"
  index=$((index + 1))
  if [ -n "$ONLY" ]; then
    case ",$ONLY," in
      *",$group,"*) ;;
      *) continue ;;
    esac
  fi
  selected_count=$((selected_count + 1))
  if run_scenario "$key"; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1))
  fi
done

if [ "$selected_count" = "0" ]; then
  printf '没有匹配的场景\n' >&2
  exit 2
fi

printf '结果：通过 %d/%d\n' "$passed" "$selected_count"
if [ "$failed" -eq 0 ]; then
  exit 0
fi
exit 1
