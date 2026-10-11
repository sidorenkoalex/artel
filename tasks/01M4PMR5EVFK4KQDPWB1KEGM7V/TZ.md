---
task: 01M4PMR5EVFK4KQDPWB1KEGM7V
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Команда Оператора pull-main — подтяжка main на verifying без возврата к роли

# ТЗ: Команда Оператора pull-main — подтянуть main в ветку задачи на verifying без возврата к роли

Источник: копилка 30.09 (приоритет 1, «Задача застревает на verifying…»),
остаток (б) строки 26.09 («команды „подтянуть main без возврата к роли“
для verifying…»), черновик docs/drafts/2026-10-05/tz-k2-verifying-red.md
(часть «команда»; вердикт по прогонам ветки — отдельная задача,
заводится параллельно). Повтор 11.10: 01M4M67SGN возвращена в in_dev
«Код не менять. Возврат только ради подтяжки main». Решение Оператора
12.10.2026 — заводить.

Факты (origin/main 3a1be8b0):
- Подтяжка main: `fsm._pull_main_or_escalate` (`orchestrator/fsm.py`
  ~202) → `orchestrator/pull.py::evaluate` (~682);
  `_doc_only_main_advance` (~658) пропускает подтяжку, если все файлы
  main после базы документные (`scripts/ci_push_class.py::is_doc_path`).
  `pull.evaluate` ставит `escalated` при конфликте, при красной планке
  после слияния (`run_plank=True`) и при несозданной рабочей копии;
  `updated_at` задачи не двигает.
- Обработчик verifying — `orchestrator/fsm_advance.py` (потолок ожидания
  от `updated_at`, отправка головы `github_adapter.ensure_head_in_origin`,
  у канарейки голова в origin не отправляется).
- Образец команды Оператора под lease — `orchestrator/ci_rerun.py`
  (`lease.run_locked`, разбор префикса id); таблица команд —
  `orchestrator/artel.py` ~1870.
- Команды «подтянуть main в ветку задачи на verifying» нет; сегодня
  единственный путь — `reject` в in_dev и шаг developer.

Требуется:
1. Новая команда Оператора `pull-main <id>`, реализация — новый модуль
   `orchestrator/pull_main.py` (по образцу `ci_rerun.py`), подключение —
   в таблице команд и справке `orchestrator/artel.py`.
2. Только в состоянии verifying; в любом другом (включая escalated после
   потолка verifying) — именованный отказ. Исполняется под lease задачи
   (`lease.run_locked`); занятый живой lease — именованный отказ.
3. Подтягивает main в ветку задачи тем же узлом
   `fsm._pull_main_or_escalate`, без пропуска по признаку «документный
   дифф main» (Оператор явно просит подтянуть); автоматическая подтяжка
   перед шагом роли не меняется. `run_plank=True` — как у подтяжки на
   переходе in_dev → verifying (`fsm_advance.in_dev`, вызов ~698): после
   слияния гоняется планка, красная планка — эскалация тем же путём.
4. После подтяжки отправляет голову в origin существующим
   `github_adapter.ensure_head_in_origin` (у канарейки — не отправляет,
   как `fsm_advance`), пишет событие в журнал задачи и оставляет задачу в
   verifying ждать CI новой головы. Состояние не меняется, кроме
   эскалации теми же путями, что у подтяжки на переходах (конфликт,
   красная планка, нет рабочей копии). Отсчёт потолка verifying
   начинается заново от подтяжки: команда пишет
   `store.update_task(conn, id, updated_at=store.now())` (store.py не
   меняется); только при исходе «подтянуто», не при «main уже в ветке» и
   не при отказе.
5. main уже в ветке — именованный ответ без события подтяжки и без push.
6. Тесты в `tests/` с заявками «Ловит мутацию»: смена состояния командой
   при успехе; пропуск подтяжки по документному диффу; отсутствие сброса потолка после
   подтяжки; работа вне verifying; работа при занятом lease; отсутствие push головы после
   подтяжки. Существующие тесты не ослабляются.

Матрица неослабления (независимая проверка 12.10): команда не двигает
состояние и не проходит гейт — после неё нужен новый зелёный CI новой
головы; конфликт и красная планка эскалируют, как сегодня; lease
исключает гонку с `auto` (ревьювер не получит голову без CI); гейт мержа
сверяет то же; сброс потолка — только явной командой Оператора и только
при новой голове, сам лимит (`VERIFYING_CEILING_SEC`) не меняется.

Зоны: orchestrator/pull_main.py, orchestrator/pull.py, orchestrator/fsm.py,
orchestrator/artel.py, tests/, docs/codebase-map.md.

Только чтение (не менять): docs/drafts/2026-10-05/tz-k2-verifying-red.md, orchestrator/ci.py, orchestrator/ci_rerun.py,
orchestrator/fsm_advance.py, orchestrator/github_adapter.py,
orchestrator/lease.py, orchestrator/fsm_merge_gate.py,
orchestrator/config.py, scripts/ci_push_class.py, conftest.py,
tests/test_invariants.py, docs/invariants.md, docs/adr/, docs/backlog.md,
docs/operator-session.md, templates/, skills/, CLAUDE.md, models.yaml,
roles.yaml, targets.yaml, .github/.

Не входит: вердикт CI по прогонам ветки (отдельная задача); подтяжка у
задачи, уже эскалированной потолком verifying; ре-ран CI вершины main;
закрытие черновых PR; изменение классификации документных путей.

Рамка: $30.

Набор моделей: по умолчанию.
