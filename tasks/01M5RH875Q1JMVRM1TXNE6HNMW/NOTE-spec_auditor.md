# Записка spec_auditor

## Выяснено
- SPEC sha 16260b89 сверен (git hash-object). Факты SPEC о коде на ad3608c6 подтвердились: строки файла волны (:47–56, :59, :71, :554–555, :558, :579), fsm_advance.py:599 (гейт планки чужого компонента без условия) и :617 (F2P под in_outcome_bounds), tests_writing.py:1090, guard.py:1628–1634/1902–1948, outcome_gate_sandbox.py:258, targets.yaml:53, config.py:132, docstring outcome_prior :6–8, 44 теста.
- Перечень методов подготовки с утверждениями у предков полон (in_dev_task, artel_in_dev_task, operator_mandate, direct_task, verifying_task, rewrite_passed, RealGitSandbox.git); refusal/no_gate_refusal файлом не зовутся.
- guard стиля pytest не запрещает box.assertIn в помощнике; _is_assertion ловит любой .assert*.
- _sandbox не зовёт tearDown; у песочниц tearDown нет.
- Вердикт: concerns (AC-11 буквально невыполним из-за setUp→git; нет AC на неассертивную часть тел тестов и «зерно не фиксируется»; заявка ac19 называет условие :617, а мутация — в гейте :599).

## Не сработало
- bash с `$f`/`;`-цепочками отклоняется песочницей — использовал python3 heredoc.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Ничего существенного.
