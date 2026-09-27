#!/usr/bin/env bash
# moneysplit 的固定验收入口。**别改这个文件。**
#
# 用法：
#   bash scripts/check.sh                 跑全部 10 个场景
#   bash scripts/check.sh -list           列出全部场景
#   bash scripts/check.sh --only kill     只跑一组（kill / hygiene / discriminate / scale）
#
# 输出：逐场景 `PASS <组>/<名>` / `FAIL <组>/<名>  期望=… 实际=…`；
#       结尾 `结果：通过 x/N`；全过 exit 0，否则 exit 1。失败不早退。
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
exec python3 check/check.py "$@"
