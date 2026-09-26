"""moneysplit —— 按权重 / 百分比 / 上限把整数金额分摊到多份。

对外只暴露这里列出的名字：

```python
from moneysplit import split, split_by_percent, allocate, merge
from moneysplit import round_half_up, round_half_even, round_floor, round_ceil
from moneysplit import InsufficientCapacity
```
"""

from .errors import InsufficientCapacity, MoneySplitError
from .rounding import round_ceil, round_floor, round_half_even, round_half_up
from .split import allocate, merge, split, split_by_percent

__all__ = [
    "InsufficientCapacity",
    "MoneySplitError",
    "allocate",
    "merge",
    "round_ceil",
    "round_floor",
    "round_half_even",
    "round_half_up",
    "split",
    "split_by_percent",
]
