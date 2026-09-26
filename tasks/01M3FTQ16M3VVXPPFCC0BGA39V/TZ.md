---
task: 01M3FTQ16M3VVXPPFCC0BGA39V
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Уборка по седьмой ревизии: карта кодовой базы с подпакетами, рудимент NoteError, пин версии CLI

# ТЗ: Уборка по седьмой ревизии: карта кодовой базы с подпакетами, рудимент NoteError, пин версии CLI

Источник: отчёт docs/audits/code-revision-2026-09-26.md, находки
CR-2026-09-26-1 (★), CR-2026-09-26-12, CR-2026-09-26-7 (часть о пине
версии). Задача вне линии провайдеров; три находки собраны в одну
задачу как малые правки без общего механизма — каждая описана
отдельным требованием со своей проверкой.

Факты (origin/main 3b56de30):
- Генератор карты scripts/codebase_map.py: `MODULE_DIRS = ("orchestrator",
  "scripts", "tests")` (:26), `discover_module_paths` берёт только
  `dir_path.glob("*.py")` (:38-46) — подпакеты orchestrator/doctor/,
  orchestrator/advance_gates/, orchestrator/providers/ (34 модуля, 7004
  строки, ~20 % оркестратора) в карту не попадают. Карту читают: CI
  (.github/workflows/ci.yml:291 — джоб перегоняет и сверяет),
  orchestrator/brief.py (перегон при подтяжке main, проекция для брифа
  роли — `MAP_PROJECTION_LABEL`, правила проекции в
  scripts/codebase_map.py::project_for_brief; алерт переполнения
  MAP_OVERSIZED_ALERT_SOURCE), гейт ёмкости (tests/test_capacity_gate_map.py),
  doctor map-growth (orchestrator/doctor/map_growth.py, порог
  config.MAP_GROWTH_RATIO = 0.25 за MAP_GROWTH_CALIBRATION_MERGES = 8
  мержей). Корень — требование SPEC T027 «модули верхнего уровня»,
  устаревшее после появления подпакетов (задачи фазы R).
- orchestrator/notes.py:96 `class NoteError(Exception)` — ни одной
  ссылки во всём дереве репозитория (grep); докстринг
  сам признаёт, что исключение нигде не ловится.
- orchestrator/config.py:256 `CLI_VERSION_PIN = "2.1.236"` (обновлён
  03.09), установлена claude 2.1.267; doctor/preflight.py:40 даёт warn
  «cli-version» на каждом шаге — 162 предупреждения за неделю по
  журналу (CR-7). Тесты читают константу: tests/test_acceptance_tests_flow.py:183,
  :978. Дедупликация предупреждений в doctor в задачу НЕ входит
  (orchestrator/doctor/ — зона задачи 6б, в полёте).

Требуется:
1. Карта с подпакетами: `discover_module_paths` обходит пакеты рекурсивно
   (`rglob("*.py")` или явный обход подкаталогов с `__init__.py`),
   dotted-имя модуля строится по пути (orchestrator.doctor.preflight),
   `__pycache__` и служебные файлы исключены; разделы карты по
   подпакетам читаемы (группировка либо префикс пакета в имени —
   выбрать и обосновать в SPEC). Перечень «Импортирует/Импортируется»
   учитывает внутрипакетные относительные импорты (`from . import x`,
   `from .. import y`). Правила проекции для брифа
   (project_for_brief) применяются к новым модулям так же, как к
   старым; итоговый размер проекции проверяется против порога алерта
   переполнения — если проекция превышает порог, правило проекции
   уточняется в том же генераторе (единственное место правил), а не
   отключается алерт.
2. Перегенерированная docs/codebase-map.md в ветке (тем же генератором,
   как делает CI и brief.regenerate) — CI-джоб codebase-map зелёный;
   doctor map-growth на этом мерже ожидаемо поднимет алерт роста
   (+34 модуля разом) — это подтверждается Оператором ack’ом, порог не
   трогать.
3. Рудимент: `orchestrator/notes.py::NoteError` удалён вместе с
   докстрингом; поведение notes не меняется (существующие
   tests/test_notes.py зелёные без правок ожиданий).
4. Пин версии CLI: `config.CLI_VERSION_PIN` поднят до "2.1.267" с
   пометкой даты и решения Оператора (26.09, по CR-2026-09-26-7);
   тесты, читающие константу, зелёные без правок; doctor cli-version
   на пульте с 2.1.267 — ok.
5. Тесты (tests/): карта содержит модули подпакетов (тест генератора на
   временном дереве с пакетом и подпакетом: оба в карте, dotted-имена
   верны, относительный импорт разрешён в перечень); проекция для брифа
   на реальном дереве не превышает порог переполнения; `NoteError`
   отсутствует в модуле; пин версии равен "2.1.267"; существующие
   tests/test_codebase_map.py, tests/test_brief.py,
   tests/test_capacity_gate_map.py, tests/test_fsm_map_regen.py,
   tests/test_review_package_map.py, tests/test_notes.py,
   tests/test_acceptance_tests_flow.py зелёные, ни один не ослаблен.

Зоны: scripts/codebase_map.py, docs/codebase-map.md,
orchestrator/notes.py, orchestrator/config.py, tests/.

Только чтение (не менять): orchestrator/advance_gates/, orchestrator/providers/ (перечисляются картой, не правятся), orchestrator/brief.py (проекция и перегон
читаются как есть; если потребуется правка — вопрос расширения зон к
Оператору), orchestrator/doctor/ (зона задачи 6б в полёте; дедупликация
предупреждений cli-version — отдельная задача), .github/workflows/ci.yml
(защищённый путь), docs/audits/code-revision-2026-09-26.md,
docs/backlog.md.

Не входит: дедупликация повторяющихся предупреждений doctor (CR-7,
вторая часть); изменение порогов map-growth и переполнения проекции;
остальные находки ревизии (CR-2, CR-3 — после мержа 6б; CR-4, CR-5 —
отдельным решением).

Рамка: $30.
