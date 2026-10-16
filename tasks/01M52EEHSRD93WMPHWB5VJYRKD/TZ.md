---
task: 01M52EEHSRD93WMPHWB5VJYRKD
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: D0-3: один источник профиля у вызывающих прогон

Родительская задача: 01M52CQB468758M2NAA15C15ZE — D0: внешний доверенный проект без песочницы — профиль чужого стека и чистое окружение тестов
Зоны: orchestrator/advance_gates/acceptance.py, orchestrator/fsm_merge_gate.py, orchestrator/suite_run.py, orchestrator/plank_run.py, orchestrator/pull.py, orchestrator/amend.py, orchestrator/notes.py, orchestrator/fsm.py, orchestrator/fsm_autogate.py, orchestrator/fsm_advance.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/test_integrity.py, tests/
Порядок: после части 2
Рамка: $40

Основание — ADR-0023, вторая поправка 16.10.2026; часть 3 из 3 задачи
D0. Опирается на приём профиля местами запуска (часть 2).

1. Вызывающие вне `acceptance.py` передают профиль проекта задачи
   (`command`, `runner`, `workdir`, `env`) тем же каналом, которым сегодня
   передаётся `command` (`Profile` вместо списка): гейт мержа
   (`fsm_merge_gate.py:962-967`), `suite-run` (`suite_run.py`, в том числе
   ключ итога `:511`, `:533`), `plank-run` (`plank_run.py:187`),
   `amend-tests` (`amend.py:545-549`, `:715-718`), прогоны `pull`
   (`pull.py:664-666`), сухой сбор `tests_writing` (`fsm_advance.py:594-596`,
   `advance_gates/tests_writing.py:557-563`), вызывающие двустороннего
   прогона (`advance_gates/test_integrity.py:1429`, `:1527`). Автогейт
   приёмки и `approve` на acceptance получают профиль через
   `acceptance.acceptance_suite` (часть 2).
2. Только передача профиля: логика гейтов и логика `suite_run.py` не
   меняются. Для прогонов без задачи (в том числе `notes.py:1040`) и для
   артели — сегодняшнее поведение. `preflight` и `acceptance-dry-run`
   pytest не запускают и не правятся.

Критерии приёмки: автогейт приёмки, `approve` на acceptance, гейт мержа и
`suite-run` запускают полный набор учебного проекта с argv, `cwd` и
окружением по профилю `pytest-own`; то же отдельно для `plank-run`,
`amend-tests`, прогонов `pull`, двустороннего прогона и сухого сбора
`tests_writing`; у артели argv, `cwd` и окружение мест запуска не
изменились. Не входит: правка `orchestrator/acceptance.py` и
`two_sided.py`; запись sled в `targets.yaml`.