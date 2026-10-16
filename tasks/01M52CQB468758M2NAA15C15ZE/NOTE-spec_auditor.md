# Записка spec_auditor

## Выяснено
- SPEC-AUDIT.md сдан: status ready, verdict concerns, spec_sha 32c4ccb8…; guard ок.
- Вызывающие с `command` вне зон: `orchestrator/fsm_advance.py:594-596`, `orchestrator/advance_gates/tests_writing.py:557-563` (сухой сбор tests_writing).
- `two_sided.run` (`two_sided.py:284`) команды не принимает; вызывающие — `test_integrity.py:1429,1527` вне зон.
- `acceptance_suite` (`acceptance.py:1807-1848`) теряет команду; в делении не принадлежит ни D0-2, ни D0-3 (D0-3 запрещает правку acceptance.py).
- `run_plank` без параметра `command`; `plank_run.py:187`, `pull.py:664-666`, `amend.py:545-549,715-718` команды не передают.
- Профиль артели несёт `command: [python3,-m,pytest]` (`targets.yaml:46`).
- Порог деления по бюджету — `config.SPLIT_SIGNAL_BUDGET_USD = 60`, а не $30, как в SPEC; строка бэклога — :186, не :185.

## Не сработало
- grep с `cd`/`$W`/пайпами требует подтверждения — только абсолютные пути, одна команда.

## Где остановился
- Работа завершена.

## Чего не хватило
- Карта не показывает вызывающих по функциям (кто зовёт `two_sided.run`, `acceptance.collect`) — искал grep'ом.
