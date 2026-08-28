---
task: T061
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Единая тестовая песочница: FakeProc, claude-only моки, TmpRootTest

## Контекст

Ревизия 28.08, находка CR-2026-08-28-2 (★5, самая дорогая,
docs/audits/code-revision-2026-08-28.md), последняя из очереди
ревизии. Второе поколение копипасты тестовых обвязок мимо общей
песочницы T037 (tests/sandbox.py):
- `FakeProc` определён 10 раз: test_git_fixation.py, test_invariants.py,
  test_agent_prompt.py, test_multitarget.py, test_multitarget_invariants.py,
  test_analyst_role.py, test_agent_log.py, test_step_cost.py,
  test_review_package.py, test_acceptance_tests_flow.py;
- claude-only side_effect (фейк только для `claude`, настоящий git) —
  4 копии: test_git_fixation.py (×2), test_doctor.py (×2); тот же класс
  недавно дважды кусался в приёмочных тестах (T051 AC-5 — двухслойная
  ловушка run/Popen);
- 6 файлов не используют sandbox.TmpRootTest и патчат СВОЁ подмножество
  путей config руками: test_brief.py, test_fsm_map_regen.py,
  test_fsm_retro.py (только ROOT/DB/TASKS), test_fsm_branch_correct_status_reads.py,
  test_gitcmd_branch_reads.py, test_retro.py — «непропатченный путь =
  тихая утечка на реальное дерево», болезнь CR-2026-08-26-3, уже
  оплаченная один раз;
- локальные fake_git: 9 в test_fsm_retro.py, 6 в test_fsm_map_regen.py,
  5 в test_brief.py при готовом sandbox.fake_git.

## Решение (Оператор 28.08, «по рекомендации» ревизии, очередь п.2б)

Донести песочницу T037 до файлов и хелперов, появившихся после неё:
(а) единый `FakeProc` и единый claude-only side_effect (фейк только
    для запуска claude через runner.spawn_agent; настоящий git — и для
    run, и для Popen, урок двухслойной ловушки T051 AC-5) — в
    tests/sandbox.py; 10 копий FakeProc и 4 копии side_effect переходят
    на импорт;
(б) шесть файлов с ручным частичным патчингом config переходят на
    sandbox.TmpRootTest с полным набором путей;
(в) локальные fake_git этих файлов — на sandbox.fake_git или общий
    параметризуемый фейк.

## Границы (правила ТЗ класса «рефакторинг», T015)

- Поведение не меняется; сценарии и ассерты тестов НЕ меняются —
  допустимы только импорты, базовые классы песочницы и пути патчей;
  ревьюер сверяет по диффу.
- PLAN: таблица переносов по файлам; откат — revert одного merge.
- Смоук: полный прогон unittest до/после с фиксацией «число тестов
  идентично, все зелёные» (текущий счёт — 820; после T060 в main
  может отличаться — зафиксировать фактический до старта).
- Никаких попутных улучшений; дедупликация только идентичных или
  заведомо эквивалентных кусков.
- Только tests/ (и tests/sandbox.py), карта не требуется (не
  orchestrator/), но если правится — тем же коммитом.

## Не входит

- Правка orchestrator/ и scripts/.
- Правка приёмочных тестов прошлых задач (tasks/*/acceptance_tests) —
  их клоны хелперов остаются как есть (залоченные каталоги).
- Изменение семантики какого-либо теста.

## Приёмка (минимум)

- `class FakeProc` определён один раз — в tests/sandbox.py; grep по
  tests/*.py подтверждает (вне tasks/).
- claude-only side_effect — единственная пара хелперов в sandbox.py
  (run и Popen), клоны в tests/*.py удалены.
- Шесть перечисленных файлов наследуются от sandbox.TmpRootTest
  (или используют его полный набор путей), ручного частичного
  патчинга config в них нет.
- Полный прогон unittest: число тестов идентично до/после, все
  зелёные, ассерты не менялись (сверка по диффу).
