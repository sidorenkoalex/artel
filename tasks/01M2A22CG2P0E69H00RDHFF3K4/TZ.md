---
task: 01M2A22CG2P0E69H00RDHFF3K4
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: канарейка читает SPEC из артефактной ветки: задача с AC-разметкой идёт в tests_writing, а не мимо test_author в in_dev

Источник: копилка docs/backlog.md, строка П1 от 12.09 «Канарейка
структурно красная на текущем пине»: прогон 20260911T230900Z
(canary-version-json, 01M29BPKYG, $3.09) снят по «3 проходов подряд без
прогресса в состоянии in_dev». Решение Оператора 12.09: чинить канарейку
задачей, затем разовый сдвиг пина.

Факты:
- `canary._spec_gate_next_state` (orchestrator/canary.py:513–523) —
  копия ветки условий `fsm._cmd_approve` для spec_gate: читает SPEC
  через `gitcmd.on_foreign_branch(t["branch"])` — с КОДОВОЙ ветки
  `task/…` либо с диска `config.TASKS/<id>/SPEC.md`. После ADR-0016
  ни там, ни там `tasks/<id>/` нет: артефакты живут только в ветке
  `artifact/<id>`. Frontmatter выходит пустым, `guard.
  requires_ac_markup({})` даёт False, задача уходит spec_gate -> in_dev
  минуя tests_writing. Так было и в зелёном прогоне 06.09
  (`.artel/canary/20260906T194847Z`, «canary: state -> in_dev» сразу
  после spec_gate): канарейка молча не проверяла test_author.
- `fsm._cmd_approve` для spec_gate (orchestrator/fsm.py:684–692) читает
  SPEC штатно: `branch, foreign = artifact_source.resolve(conn,
  task_id)`; при foreign — `_read_branch_text_or_refuse(conn, task_id,
  branch, "SPEC.md")`, иначе `artifacts.frontmatter(config.TASKS /
  task_id / "SPEC.md")`. Тот же приём у гейта планки
  `fsm_advance._acceptance_run_refuses._missing_plank_refuses`
  (строки 1131–1145).
- Гейт «планка не найдена в источнике» (01M283NJV2, коммит 9ad1ae90,
  в main с 22:01 11.09, в пине 699fa124 уже есть) отказывает на выходе
  in_dev, если артефактная ветка не несёт acceptance_tests/ и SPEC
  требует AC-разметку. Канареечная задача с AC-1..AC-4 в SPEC, но без
  test_author, получает три отказа и снимается.
- Канарейка тестирует код пина (`canary.py:995`: `main_sha =
  gitcmd.head_sha()`); `pin.cmd_pin_update` требует зелёный прогон не
  старше `CANARY_MAX_MERGES_SINCE_GREEN = 10` мержей (сейчас 13).
  Разовый сдвиг пина после мержа этой правки — решение Оператора вне
  задачи.
- Модуль canary.py намеренно не зовёт `cmd_approve` (модульный
  докстринг), копия ветки условий остаётся; меняется только источник
  SPEC.

Требуется:
1. `canary._spec_gate_next_state` читает SPEC тем же путём, что `fsm._cmd_approve` для spec_gate: `artifact_source.resolve(conn, task_id)`; при foreign — текст SPEC с артефактной ветки (`gitcmd.show(branch, f"tasks/{task_id}/SPEC.md")` либо `fsm._read_branch_text_or_refuse`, если импорт не заводит цикл — иначе тем же приёмом инъекции, что у pull.py), иначе `artifacts.frontmatter(config.TASKS / task_id / "SPEC.md")`; `gitcmd.on_foreign_branch(t["branch"])` для SPEC больше не используется.
2. SPEC не найден ни в одном источнике — канарейка не трактует это как «без AC-разметки»: `_pass_spec_gate` зовёт `_kill_inconclusive` с текстом «canary: SPEC не найден в источнике артефактов (<ветка>)», прогон помечается red с этой причиной, а не тихим переходом в in_dev.
3. В отчёт прогона канарейки (строка задачи с «шагов=… исход=…») добавляется признак, прошла ли задача tests_writing: «test_author=да/нет», чтобы пропуск стадии был виден в отчёте, а не только в steps.txt.
4. Тесты в tests/test_canary.py: `_spec_gate_next_state` для задачи, чей SPEC с `schema_version: 2` и AC-разметкой лежит только в артефактной ветке (стенд по образцу существующих тестов канарейки/artifact_source), возвращает «tests_writing» (мутация «чтение с кодовой ветки» — красный); SPEC с `skip_tests: <причина>` — «in_dev»; SPEC отсутствует — `_kill_inconclusive` с названной причиной, не «in_dev»; отчёт прогона несёт «test_author=…»; существующие тесты канарейки — без ослабления.

Зоны: orchestrator/canary.py, tests/.

Приложением: orchestrator/fsm.py (_cmd_approve, spec_gate), orchestrator/artifact_source.py, orchestrator/fsm_advance.py (_missing_plank_refuses), .artel/canary/20260911T230900Z/01M29BPKYG5841MGMPHZVPCBEP/steps.txt (журнал красного прогона), docs/backlog.md (строка П1 от 12.09).

Условие старта: зона orchestrator/canary.py занята задачей 01M29284PT до её мержа (сейчас merge_gate); шаг разработчика подождёт.

Не входит: сдвиг пина и изменение порога `CANARY_MAX_MERGES_SINCE_GREEN`; правка `pin.py`; синтетическое прохождение tests_writing канарейкой (test_author идёт по-настоящему, как и остальные роли); правка fsm.py и fsm_advance.py.

Рамка: $30.
