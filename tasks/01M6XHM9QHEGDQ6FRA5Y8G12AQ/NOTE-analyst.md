# Записка analyst

## Выяснено
- ТЗ хватило на SPEC без вопросов. SPEC.md написан, guard: ок. В нём 6 критериев AC-1..AC-6, у AC-2 восемь случаев загрязнения. budget_usd 45: рамка ТЗ $60, дефолт 50, по калибровке это класс «до 10 критериев».
- Ссылки ТЗ на код сходятся с main: tests/fixtures.py::_sandbox :42, _run_cleanups :20; tests/sandbox.py ALL_CONFIG_ATTRS :91, TmpRootTest :1605, PATCHED_ATTRS :1623, RealGitSandbox :1921; инвариант 42 — tests/test_invariants.py:3466.
- Сигналы деления не сработали: порог бюджета SPLIT_SIGNAL_BUDGET_USD = 60, у SPEC 45; критериев 6 при пороге 10; зон 3.
- Требование 6 (метка pytest.mark.size) условное: оно действует, только если этап 4 ADR-0032 попадёт в main раньше, чем задача выйдет из tests_writing.

## Не сработало
- Bash с `cd` или переменной пути и пайпом отклоняется. Работают Read и одиночный grep по абсолютному пути.

## Где остановился
- Шаг закончен, SPEC status: ready.

## Чего не хватило
- Ничего.
