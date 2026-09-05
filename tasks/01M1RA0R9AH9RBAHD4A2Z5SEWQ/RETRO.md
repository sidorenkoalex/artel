---
operator: Alexander Sidorenko
model: unknown
artel_sha: a5c464d6dfe12efd116122504dc60b8171867b4a
---

# RETRO: 01M1RA0R9AH9RBAHD4A2Z5SEWQ — Перегенерированная карта после шага роли не ломает подтяжку main

Итог: killed — причина: причина не найдена в журнале
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: Перегенерированная карта после шага роли не ломает подтяжку main

Стоимость итого: $23.12
  analyst: $2.23, 3583876 токенов
  test_author: $6.99, 14631332 токенов
  developer: $10.77, 21968409 токенов
  reviewer: $3.12, 5826038 токенов

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 2 (последняя): эскалация от разработчика: ### Вопросы

1. (блокирует зелёную планку целиком) Два дефекта локального
   приёмочного фикстура `tasks/01M1RA0R9AH9RBAHD4A2Z5SEWQ/
   acceptance_tests/_sandbox.py` (общий для всех пяти test_*.py файлов
   планки, локальная песочница без реального git — тот же приём, что
   `tests/test_fsm_map_conflict_autoresolve.py`) не позволяют получить
   зелёный AC-3/AC-4/AC-5 без правки локального файла, которую роль
   `developer` делать не вправе (T023):
   - `_sandbox.py::PullCleanupSandbox.advance_from_in_dev` не пишет на
     диск `tasks/<id>/SPEC.md` и `tasks/<id>/acceptance_tests/` ДО
     перехода — в отличие от `tests/test_fsm_map_conflict_
     autoresolve.py::write_acceptance_plank`/`tests/
     test_branch_freshness_gate.py::write_acceptance_plank`, чей
     докстринг прямо объясняет, зачем это обязательно для лёгкой
     песочницы (`disk_backed_show`/`disk_backed_ls_tree_files` читают
     ветку с диска `config.TASKS`, не из настоящего git). Без плашки
     `_pull_main_or_escalate` (fsm.py:384-406, существующая логика SPEC
     01M1R9YEK08XEQWBFX0929WFVJ, вне зон этой задачи) честно видит
     отсутствующий `SPEC.md` на «ветке» и возвращает `"refused"` —
     переход не происходит, состояние остаётся `in_dev`. Это не дефект
     кода этой задачи: с плашкой (проверено локальной правкой
     `_sandbox.py` только для диагностики, затем возвращено к
     исходному виду) AC-3 зеленеет немедленно.
   - После добавления плашки AC-4/AC-5 всё равно падают — на этот раз
     на `acc_run.assert_called_once_with(self.wt_path / "tasks" /
     self.TASK)` (test_ac1_ac4_map_only_dirty_discarded.py:138,
     test_ac2_ac3_ac5_wip_checkpoint.py:168): ожидаемый вызов не несёт
     `code_root=...`, а текущий (и единственно верный, ADR-0013,
     hotfix 88b38022, `tests/test_branch_freshness_gate.py` проверяет
     это же явно) контракт `acceptance.run(tdir, code_root=wt_path)`
     требует этот именованный аргумент — без него планка теряет код
     задачи и годами читает пин вместо ветки (та самая регрессия,
     которую чинил hotfix). Понижать вызов до `acceptance.run(tdir)`
     было бы ослаблением уже починенного дефекта — запрещено
     принципом целостности.

   Оба дефекта — в локальном `_sandbox.py`, который test_author писал
   без плашки-фикстуры (в отличие от двух других задач с той же
   механикой) и с устаревшим (пред-ADR-0013) ожиданием сигнатуры
   `acceptance.run`. Варианты: (а) test_author правит `_sandbox.py`
   каналом `amend-tests` — добавляет `write_acceptance_plank`-подобный
   метод (по образцу `tests/test_fsm_map_conflict_
   autoresolve.py::write_acceptance_plank`) в `advance_from_in_dev` и
   правит два `assert_called_once_with` на `code_root=self.wt_path`;
   (б) Оператор считает диагностику неверной и указывает другую
   причину. Дефолт при молчании — (а): фиксирую эскалацию, следующий
   шаг test_author правит планку через `amend-tests`.

### Контекст

- Реализация требований 1-4 (`orchestrator/fsm.py::
  _pull_main_or_escalate`, `orchestrator/checkpoint.py::
  commit_pull_checkpoint`) уже в коде ветки (коммит 77f3cfc1) —
  ANSWER-1 подтверждает, что AC-1/AC-4/AC-6 были зелёными на этом
  коммите; AC-2 (проверяет только факт commit-вызова и текст журнала,
  без сверки итогового состояния) зелен и сейчас.
- Три существующих модуля юнит-тестов, которые правка затрагивает
  напрямую и не имеет права ослаблять (AC-8), зелёные полным прогоном:
  `python3 -m unittest tests.test_timeout_checkpoint
  tests.test_fsm_map_conflict_autoresolve
  tests.test_branch_freshness_gate` — 47/47 OK, включая
  `test_branch_freshness_gate.py::test_approve_refuses_when_spec_
  read_fails_after_missing_plank`, который проверяет ИМЕННО этот
  `"refused"`-путь как корректное поведение при отсутствующей плашке.
- Диагностика дефектов `_sandbox.py` — временная локальная правка
  `advance_from_in_dev` (добавлен вызов метода, пишущего SPEC.md +
  `acceptance_tests/test_stub.py` на диск перед `set_state("in_dev")`,
  по образцу `write_acceptance_plank` соседних файлов), прогон планки,
  откат правки к исходному тексту — итоговый `_sandbox.py` в рабочем
  каталоге сейчас идентичен полученному в брифе роли.

### Блокирует

AC-3/AC-4/AC-5 не могут стать зелёными без правки локального
`acceptance_tests/_sandbox.py` и двух `assert_called_once_with` в
test_ac1_ac4/test_ac2_ac3_ac5 — правка локального файла вне мандата
роли `developer` (T023, «их правка — эскалация, не правка»). Готовую
реализацию (требования 1-5, AC-1/AC-2/AC-6/AC-7 зелёные, три сторонних
модуля юнит-тестов зелёные) сдать под `status: ready` при красной
локальной планке нельзя.

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
