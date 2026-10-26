---
task: 01M5W27CY7K7NR9347NKD8F0NX
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: GitLab А0: неподдержанный хостинг или гейт людей проекта — именованный отказ до первой задачи

# GitLab, шаг А0: проект с неподдержанным хостингом или гейтом мержа людьми проекта — именованный отказ до первой задачи

## Факты

ADR-0029 (принят 26.10.2026), п. 8: «Первой задачей: загрузка записи с `merge_gate: target-human` или с `forge` без адаптера отказывает с причиной — до исполнения остальных пунктов».

1. `orchestrator/targets.py:23-24` — `FORGES = ("github", "gitlab")`, `MERGE_GATES = ("operator", "target-human")`; проверка записи (`targets.py:622-628`) принимает оба значения. Исполняются только `github` и `operator`.
2. С записью `forge: gitlab` или `merge_gate: target-human` сейчас: черновой MR для не-GitHub молча пропускается (`orchestrator/github_adapter.py:133`); ожидание CI ветки идёт через `gh` (`orchestrator/ci.py`) и для GitLab не работает; `approve` на `merge_gate` (`orchestrator/fsm.py:1611` `_approve_merge_gate`) вливает ветку в `base` и отправляет основную ветку (`fsm_merge_gate._push_merged_main`) при любом `merge_gate` — для проекта с гейтом людьми проекта пульт смержил бы сам.
3. Существующие тесты заводят записи с `forge: gitlab` и `merge_gate: target-human` как данные загрузки и уборки: `tests/test_coldstart.py:137`, `tests/test_multitarget.py:202`, `tests/test_01m5scgsqn0at0b07h7m9803ra_local_layer.py:229`, `tests/test_doctor.py:671`, `tests/test_github_adapter.py:82,313`, `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py:870`. Отказ на загрузке записи сломал бы чтение записей, `doctor` и уборку, которые сами по себе безопасны.

## Требуется

1. **Одна функция поддержки.** В `orchestrator/targets.py` — константы исполняемых значений `SUPPORTED_FORGES = ("github",)` и `SUPPORTED_MERGE_GATES = ("operator",)` и функция `unsupported_reason(name) -> str | None`: причина «хостинг <forge> не поддержан: адаптера нет (ADR-0029)» или «гейт мержа target-human не исполняется (ADR-0029)», иначе `None`. Расширять константы будут задачи А1 и Б2 — одной строкой каждая.
2. **Отказ на действиях, ведущих к задаче, отправке и мержу** (запись по-прежнему загружается, читается, `doctor` и уборка работают):
   - `new … --target <проект>` — до заведения задачи и номера, без побочных эффектов;
   - `run` и `auto` задачи такого проекта — до запуска агента и до подтяжки (`runner.cmd_run` и вход `auto`);
   - `approve` в любом состоянии задачи такого проекта — до гейта (`fsm.cmd_approve`);
   - каждый отказ — именованный, с причиной `unsupported_reason`, с записью журнала задачи (у `new` — без задачи: только вывод и код выхода, как у прочих отказов `new`).
3. **`doctor`** — строка `project-support-<проект>`: `fail` с той же причиной для записи с неподдержанным значением, `ok` — для поддержанной; у артели — `ok`.
4. Порядок проверок не меняется для поддержанных проектов: вывод `new`, `run`, `approve`, `doctor` для `github` + `operator` — прежний.

Критерии приёмки:
- запись `forge: gitlab` (и отдельно `merge_gate: target-human`) загружается `targets.target`, а `new --target` отказывает с причиной, задача не заведена (число строк `tasks` и `steps` не изменилось);
- задача такого проекта, заведённая в БД фикстурой, — `run` отказывает до `spawn_agent` и до вызовов git; `approve` на `merge_gate` отказывает до слияния (шпион git: нет `merge`, нет `push`), запись журнала с причиной;
- `doctor` — `project-support-<проект>` `fail` с причиной; для `github` + `operator` — `ok`;
- проект `github` + `operator`: `new`, `run`, `approve` на `merge_gate` проходят как раньше (существующие тесты зелёные без правки);
- `unsupported_reason` — единственное место списка поддержанных значений (тест-сторож: литералов `"gitlab"`/`"target-human"` в проверках поддержки вне `targets.py` нет).

Зоны: `orchestrator/targets.py`, `orchestrator/catalog.py`, `orchestrator/runner.py`, `orchestrator/auto.py`, `orchestrator/fsm.py`, `orchestrator/doctor/` (новая строка проверки и её регистрация), `tests/` (долгоживущие файлы задачи).

Только чтение: `orchestrator/github_adapter.py`, `orchestrator/ci.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/cleanup.py`, `docs/adr/0029-external-delivery-via-mr.md`, `docs/adr/0003-target-projects.md`.

Существующие тесты: правка — по мандату Оператора 26.10 на тесты, которые меняет ADR-0029 (без ослабления, с матрицей и независимой проверкой) через гейт SPEC; ожидается, что правка не нужна — записи с `gitlab`/`target-human` в существующих тестах только загружаются и убираются.

Не входит: адаптер GitLab (А1); исполнение `target-human` (Б2); поля ветки и коммитов (Б1).

Рамка: $15. Набор моделей — по умолчанию.
