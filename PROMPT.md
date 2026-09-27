这批用例的价值在于它们能不能把实现里的差异问出来。moneysplit 是 Python 3 的金额分摊库，
只用标准库（unittest 跑用例），没有第三方依赖，自检走 `bash scripts/check.sh`
（`mutcheck.py` 是固定验收程序，别改）。

README 有「不变式」5 条、「设计说明」一节和「用例要求」一节；`moneysplit/` 下是完整实现，
`tests/` 里 3 个冒烟用例当前全绿 —— 但按固定件算出来的杀伤率只有 0.32。

任务：补齐 `tests/` 下的用例，把杀伤率提到阈值以上，并让区分性要求也满足，固定件全过。

验收：
- python3 -m unittest discover -s tests 退出码 0（用例自身必须全绿）；
- bash scripts/check.sh 退出码 0，10 个场景全过（kill 3 + hygiene 3 + discriminate 2 + scale 2）。

约束：
1. 不改 `mutcheck.py`、不改 `moneysplit/` 下的实现；只在 `tests/` 下加用例。
2. 只通过公开 API 观察行为，不许读源码、字节码、文件哈希、行号。
3. 不许用 sleep / 随机 / 时间让用例凑巧通过。
4. 用例数量与组织方式见 README「用例要求」。
