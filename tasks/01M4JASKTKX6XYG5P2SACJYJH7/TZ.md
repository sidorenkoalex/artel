---
task: 01M4JASKTKX6XYG5P2SACJYJH7
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Порядок старта в очереди зоны

# ТЗ: Порядок старта в очереди зоны — очередь Оператора и merge_after решают, кто стартует

Источник: строка бэклога «Порядок старта в очереди зоны» (приоритет 1,
решение Оператора 05.10); черновик `docs/drafts/2026-10-05/tz-k1-zone-order.md`;
решение Оператора 10.10.2026 — заводить.

Случаи:
- 05.10 утро: часть 3 этапа 3 (01M45FKEQ6, merge_after = часть 2) первой
  закончила тесты и заняла зону orchestrator/ шагом разработчика, часть 2
  ждала зону — взаимная блокировка, часть 3 ликвидирована.
- 05.10 17:14Z: после мержа 01M462QACE зону взяла 01M46D5ZZQ (позиция 4,
  зона orchestrator/ci.py), а 01M46C776S (позиция 1) и 01M46D5T8S (позиция
  2) остались ждать; `zone-reorder` печатает «переставлена», но старт не
  решает.
- 05.10: деление задачи на гейте SPEC (01M45FJD46 → подзадачи) переводит
  родителя в killed, а merge_after зависящих задач остаётся на нём —
  гейт мержа зависящей задачи отказывает «зависимость убита».

Факты (main eccf5709, сверка 10.10):
- `orchestrator/zone_lock.py::blocking_conflict` (~398) и `claim` (~459)
  решают только по занятости зоны (`_occupies` ~349); ожидающие задачи,
  `queue_order` и `merge_after` не учитываются.
- `queue_order` (~567): `zone_queue_position`, затем время approve SPEC,
  затем `updated_at`; `queue_position` (~590) только показывает порядок и
  считает конкурентами задачи с ТОЧНО тем же путём (`conflict[0] == path`,
  ~609) — вложенные зоны (orchestrator/ и orchestrator/ci.py) попадают в
  разные очереди; пересечение путей — `_paths_overlap` (~204).
- `cmd_zone_reorder` (~617) пишет `zone_queue_position` и печатает
  «переставлена» (~625); без аргументов тоже печатает «переставлена».
- `orchestrator/fsm.py::_spawn_division_subtasks` (~819) ставит родителю
  killed («поделена на: …»), merge_after других задач не переписывает;
  `orchestrator/merge_after.py::check` (~126) и `merge_gate_refuses`
  (~387) отказывают на killed-зависимости; `merge_after.rewrite` (~286)
  уже существует.
- Ожидание зоны внутри `auto` штатное (`config.AUTO_WAIT_ZONE_DEFAULT`,
  опрос `ZONE_WAIT_POLL_SEC` = 90 с) — 09.10 01M4FYTB8QWJNHYCP35K8QC4E3
  дождалась зону и стартовала сама.

Требуется:
1. Зону, которую никто не держит, получает первая по очереди задача среди
   ожидающих пересекающуюся зону (с учётом вложенности путей,
   `_paths_overlap`); остальные получают именованный отказ «ждёт очереди
   зоны: впереди <id>».
2. Порядок очереди: ручной `zone-reorder` главнее; без него — зависимость
   раньше зависящей задачи (топологический порядок по merge_after), затем
   нынешние ключи. Задача, у которой незавершённая зависимость merge_after
   ждёт пересекающуюся зону, зону не получает (отказ «ждёт зону ради
   зависимости <id>»).
3. Ожидающая задача, которая сама не может стартовать (цикл не идёт,
   пауза, эскалация), очередь не держит.
4. `queue_position`, `status` и `doctor` показывают ту же очередь, что
   решает старт; `zone-reorder` без аргументов — отказ с подсказкой.
5. Деление задачи на гейте SPEC переписывает merge_after задач, зависящих
   от родителя, на последнюю подзадачу деления (через `merge_after.rewrite`,
   с записью журнала «было → стало»).
6. Смена поведения существующих тестов — только разделом SPEC
   «Меняемое поведение» (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- Перестановка `zone-reorder` меняет, кто стартует первым, в том числе
  при вложенных зонах.
- Цепочка из трёх задач с merge_after на одной зоне проходит без
  взаимной блокировки: зависимость стартует раньше зависящей.
- Ожидающая задача на паузе или без живого цикла очередь не держит.
- `status`/`doctor` показывают тот же порядок, что решает старт.
- Деление на гейте SPEC переписывает merge_after зависящей задачи на
  последнюю подзадачу, журнал называет «было → стало».

Зоны: orchestrator/zone_lock.py, orchestrator/fsm.py,
orchestrator/merge_after.py, orchestrator/catalog.py, orchestrator/doctor/,
docs/codebase-map.md, tests/.

Только чтение (не менять): orchestrator/runner.py, orchestrator/auto.py,
orchestrator/lease.py, orchestrator/checkpoint.py, orchestrator/alerts.py,
scripts/guard.py, orchestrator/advance_gates/, tests/test_invariants.py,
docs/invariants.md, docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, docs/drafts/, templates/, skills/, CLAUDE.md,
models.yaml, roles.yaml, targets.yaml, .github/workflows/ci.yml, .artel/.

Не входит: orchestrator/ и orchestrator/ci.py — в разделе «Случаи» это
примеры зон других задач, в эту задачу как зоны не входят; замок полного прогона; наследование набора моделей
подзадачами деления (копилка 08.10, отдельная строка); поле «Порядок:»
в ТЗ.

Рамка: $60.

Набор моделей: по умолчанию.
