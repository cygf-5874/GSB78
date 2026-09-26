# moneysplit —— 整数金额分摊

`moneysplit` 是一个纯标准库的 Python 3 小库：把**整数分**按权重、百分比或上限分摊到若干份，
并保证「分出去的和 = 分进来的总额」。它只跟 `int` 打交道，不做浮点近似，
同一组输入永远得到同一组输出。

```python
from moneysplit import split, split_by_percent, allocate, merge

split(100, [1, 1, 1])            # [34, 33, 33]   最大余数法，余数并列按索引升序
split(-100, [1, 1, 1])           # [-34, -33, -33]  退款：按绝对值分摊后整体取负
split_by_percent(101, [50, 50])  # [51, 50]       余数给第一个非零份额
allocate(5, [2, 10])             # [1, 4]         每份不超过上限
merge([34, 33, 33])              # 100            与 split 互逆
```

## 目录

```
moneysplit/
  __init__.py   对外导出
  errors.py     MoneySplitError / InsufficientCapacity
  split.py      split / split_by_percent / allocate / merge
  rounding.py   round_half_up / round_half_even / round_floor / round_ceil
tests/          用例（起点只有 3 个冒烟用例）
mutcheck.py     变异测试入口（**固定件，勿改**）
scripts/check.sh  固定验收入口（**固定件，勿改**）
```

## 对外 API

```python
split(total_cents: int, weights: list[int]) -> list[int]
split_by_percent(total_cents: int, percents: list[int]) -> list[int]
allocate(total_cents: int, caps: list[int]) -> list[int]
merge(parts: list[int]) -> int

round_half_up(value) -> int      # value 是 int 或 fractions.Fraction
round_half_even(value) -> int
round_floor(value) -> int
round_ceil(value) -> int
```

## 语义清单（12 条）

下面每一条都是对外契约，实现与用例都要守住。

1. **分摊**：`split(total_cents, weights)` 按权重把总额分摊到 `len(weights)` 份，返回整数分列表。
2. **总和守恒**：返回值的和**恒等于** `total_cents`（正负都成立），一分不多一分不少。
3. **最大余数法**：先各取 `floor`，剩下的整数分按**余数从大到小**逐份加 1；
   余数相同时按**索引升序**优先。
4. **权重**：权重必须非负；权重全为 0 时退化成**均分**，余数同样按索引升序分发。
5. **负总额（退款）**：`total_cents` 为负时按**绝对值**分摊，再把每份取负，
   结果**仍然守恒**。
6. **舍入四模式**：`round_half_up`（半值朝 +∞）/ `round_half_even`（半值向偶数）/
   `round_floor`（向下）/ `round_ceil`（向上），入参是精确有理数，返回 `int`。
7. **百分比**：`split_by_percent(total, percents)` 的百分比之和必须是 `100` 或 `1`
   （两种写法都接受）；先各取 `floor`，剩下的整数分**全部给第一个非零份额**。
8. **带上限分摊**：`allocate(total, caps)` 的每一份都不超过 `caps[i]`；
   容量（`caps` 之和）不足时抛 `InsufficientCapacity`，异常携带「还差多少」的数量。
9. **边界**：单元素、空列表、`total = 0` 都是合法输入；`weights` 为空且 `total != 0` 抛 `ValueError`。
10. **互逆**：`merge(parts)` 返回各份之和，与 `split` 互逆（`merge(split(t, w)) == t`）。
11. **只收 int**：`total_cents`、权重、上限、百分比出现 `float` / `Decimal` 时一律抛 `TypeError`，
    不接受近似值。
12. **纯函数**：不依赖随机源、时间、字典迭代顺序或任何全局状态；同输入同输出。

## 用例要求

这一节同时是对 `tests/` 下用例的硬性要求。

- 用例放在 `tests/` 下，`python3 -m unittest discover -s tests` 要能跑；
- **只能通过公开 API 观察行为差异**：只用 `moneysplit` 包根导出的名字，
  不许读私有符号（`_` 前缀），不许依赖内部存储结构；
- 不许读实现源码 / 字节码 / 文件内容，不许用 `inspect` / `dis` / `hashlib` / `__file__`，
  不许比对文件哈希或行号，也不许用「实现有没有被改过」这类和语义无关的信号判胜负；
- 不许用 `sleep` / 随机数 / 时间让用例「碰巧」通过；输入写死，每次跑结果一致；
- 用例名要能看出在测语义清单里的哪一条；
- **规模**：至少 **40 个**用例（按语义清单分堆组织）；
- 目标：`mutcheck.py` 的杀伤率 ≥ **0.90**。

## 怎么跑

```bash
python3 -m unittest discover -s tests   # 跑用例
python3 mutcheck.py                     # 变异检查：打印杀伤率，低于 0.90 退出码为 1
python3 mutcheck.py --list              # 只列变异位点
python3 mutcheck.py --jobs 4 --timeout 5
bash scripts/check.sh                   # 固定验收入口（8 个场景）
bash scripts/check.sh -list             # 列出全部场景
bash scripts/check.sh --only kill       # 只跑一组（kill / hygiene / scale）
```

`mutcheck.py` 对 `moneysplit/` 下的实现做 AST 级**单点变异**——每次只把一处运算或常量
改成写法相近的错误写法，再用 `tests/` 下的用例去杀：用例红了算**杀掉**，用例还是绿的算**存活**。
它最后打印杀伤率（被杀 / 全部位点）和存活清单。变异体超时按「被杀」计。
`scripts/check.sh` 在 `mutcheck.py` 之外还检查用例自身的卫生（hygiene）、规模与全量检查耗时。

## 版本前提

- Python 3.9 及以上（开发与实测用 3.13），只用标准库
  （`math`、`fractions`、`unittest`、`argparse`、`ast`、`subprocess`、`threading`、`shutil`、`tempfile`、`time`）。
- 没有第三方依赖，没有 `requirements.txt`，不需要联网、不需要数据库、不起中间件。
- 判据是确定性的：固定输入、固定期望输出；`scale` 组读一次墙钟，上限写死在
  `scripts/check.sh` 的 `MAX_SECONDS = 60`（实测在本机 10 秒上下），跑题机更慢时按比例放宽。
