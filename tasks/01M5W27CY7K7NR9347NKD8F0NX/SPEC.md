---
task: 01M5W27CY7K7NR9347NKD8F0NX
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/targets.py, orchestrator/catalog.py, orchestrator/runner.py, orchestrator/auto.py, orchestrator/fsm.py, orchestrator/doctor/, tests/
budget_usd: 25
---

# SPEC: GitLab А0 — неподдержанный хостинг или гейт людей проекта: именованный отказ до первой задачи

## Контекст
ADR-0029 (принят 26.10.2026), п. 8: первой задачей запись с `merge_gate:
target-human` или с `forge` без адаптера должна отказывать с причиной — до
исполнения остальных пунктов ADR. Сейчас `orchestrator/targets.py:23-24`
(`FORGES = ("github", "gitlab")`, `MERGE_GATES = ("operator",
"target-human")`) и проверка записи принимают оба значения, хотя исполняются
только `github` и `operator`: черновой MR для не-GitHub молча пропускается
(`orchestrator/github_adapter.py:133`), ожидание CI идёт через `gh`
(`orchestrator/ci.py`), а `approve` на `merge_gate`
(`fsm._approve_merge_gate`) вливает ветку в `base` и отправляет её
(`fsm_merge_gate._push_merged_main`) при любом `merge_gate` — для проекта с
гейтом людьми проекта пульт смержил бы сам. Отказ на загрузке записи сломал
бы чтение записей, `doctor` и уборку, которые безопасны, и существующие
тесты, заводящие такие записи как данные (`tests/test_coldstart.py:137`,
`tests/test_multitarget.py:202`,
`tests/test_01m5scgsqn0at0b07h7m9803ra_local_layer.py:229`,
`tests/test_doctor.py:671`, `tests/test_github_adapter.py:82,313`,
`tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py:870`) —
поэтому отказ ставится на действия, ведущие к задаче, отправке и мержу.

## Требования

1. **Одна функция поддержки.** В `orchestrator/targets.py` есть константы
   исполняемых значений `SUPPORTED_FORGES = ("github",)` и
   `SUPPORTED_MERGE_GATES = ("operator",)` и функция
   `unsupported_reason(name) -> str | None`, возвращающая для проекта `name`
   причину «хостинг <forge> не поддержан: адаптера нет (ADR-0029)» (значение
   `forge` записи вне `SUPPORTED_FORGES`) или «гейт мержа target-human не
   исполняется (ADR-0029)» (значение `merge_gate` вне
   `SUPPORTED_MERGE_GATES`), иначе `None`. Списки поддержанных значений
   живут только в этих константах: расширение (задачи А1 и Б2) — одна
   строка в каждой.
2. **Запись по-прежнему загружается.** Запись с `forge: gitlab` или с
   `merge_gate: target-human` загружается `targets.target` и читается;
   `doctor` и уборка для такой записи работают как раньше.
3. **Отказ `new`.** `new … --target <проект>` для проекта, у которого
   `unsupported_reason` не `None`, отказывает до заведения задачи и номера,
   без побочных эффектов: проверка в `catalog.cmd_new` стоит ДО
   `workspace.ensure_clone` (`catalog.py:829`) и до выдачи id
   (`idgen.new_task_id`, `catalog.py:838`) — клон проекта не создаётся, git
   не вызывается, строки `tasks`/`steps` не меняются. Именованный отказ с
   причиной `unsupported_reason` — вывод и ненулевой код выхода, как у
   прочих отказов `new` (задачи нет — записи журнала задачи нет).
4. **Отказ `run` и `auto`.** `run` задачи такого проекта отказывает в
   `runner.cmd_run` до запуска агента и до подтяжки. `auto` отказывает на
   ВХОДЕ (`auto.cmd_auto`/`auto._cmd_auto`) — до `_pre_advance_step`, до
   `fsm.cmd_advance`, до опроса CI и до любого вызова git. Оба отказа —
   именованные, с причиной `unsupported_reason` и записью журнала задачи.
5. **Отказ `approve`.** `approve` в любом состоянии задачи такого проекта
   отказывает до гейта (`fsm.cmd_approve`) — именованный отказ с причиной
   `unsupported_reason` и записью журнала задачи.
6. **`doctor`.** `doctor` выводит строку `project-support-<проект>`: `fail`
   с причиной `unsupported_reason` для записи с неподдержанным значением,
   `ok` — для поддержанной; у артели — `ok`.
7. **Поддержанные проекты — без изменений.** Для проекта `github` +
   `operator` порядок проверок и вывод `new`, `run`, `approve`, `doctor`
   прежние (кроме новой строки `project-support-<проект>` `ok`).

## Критерии приёмки

AC-1. Запись `forge: gitlab` (и отдельно запись `merge_gate:
target-human`) загружается `targets.target` без исключения;
`targets.unsupported_reason` возвращает для неё соответственно «хостинг
gitlab не поддержан: адаптера нет (ADR-0029)» и «гейт мержа target-human не
исполняется (ADR-0029)», для записи `github` + `operator` — `None`;
`targets.SUPPORTED_FORGES == ("github",)`, `targets.SUPPORTED_MERGE_GATES ==
("operator",)`.

AC-2. `new --target <проект>` для записи `forge: gitlab` (и отдельно для
записи `merge_gate: target-human`) отказывает с ненулевым кодом выхода и
причиной `unsupported_reason` в выводе, без побочных эффектов: каталог
клона проекта (`repo_context.clone_path`) после вызова отсутствует, шпион
git не видит ни одного вызова, строки `tasks` и `steps` в БД до и после
вызова одинаковы.

AC-3. Задача проекта с неподдержанным значением, заведённая в БД
фикстурой: `run` отказывает с причиной `unsupported_reason` до
`spawn_agent` и до любого вызова git (шпионы: ни одного вызова), в журнале
задачи — запись с этой причиной.

AC-4. Для той же задачи `auto` отказывает на входе с причиной
`unsupported_reason`: шпионы `fsm.cmd_advance` и git не видят ни одного
вызова (отказ раньше `_pre_advance_step`, опроса CI и подтяжки), в журнале
задачи — запись с этой причиной.

AC-5. Задача проекта с неподдержанным значением в состоянии `merge_gate`:
`approve` отказывает с причиной `unsupported_reason` до слияния — шпион git
не видит ни `merge`, ни `push`; состояние задачи осталось `merge_gate`; в
журнале задачи — запись с этой причиной.

AC-6. Задача проекта с неподдержанным значением в состоянии другого гейта
(`spec_gate`): `approve` отказывает с причиной `unsupported_reason`,
состояние задачи не изменилось, в журнале задачи — запись с этой причиной.

AC-7. `doctor` для записи с неподдержанным значением выводит строку
`project-support-<проект>` со статусом `fail` и причиной
`unsupported_reason`; для записи `github` + `operator` и для артели — строку
`project-support-<проект>` со статусом `ok`.

AC-8. Проект `github` + `operator`: `new`, `run` и `approve` на
`merge_gate` проходят как раньше — существующие тесты этих команд и файлы
из «Контекста», заводящие записи `gitlab`/`target-human`, не изменены
веткой задачи.

AC-9. Тест-сторож: во всём `orchestrator/` кроме `orchestrator/targets.py`
нет сравнения значения поля `forge` или `merge_gate` с литералом
поддержанного или неподдержанного значения (`"github"`, `"gitlab"`,
`"operator"`, `"target-human"`) в проверках поддержки — `unsupported_reason`
единственное место списка поддержанных значений. Исключения — существующие
сравнения `forge` с `"github"` вне проверки поддержки (раздел «Исключения
сторожа AC-9»); сторож их называет поимённо и не требует переписывать.

## Исключения сторожа AC-9
Существующие сравнения поля `forge` с `"github"` на main, которые выбирают
поведение GitHub-адаптера, а не решают, поддержан ли проект; ветка задачи
их не переписывает:

- `orchestrator/github_adapter.py:62` — `_is_github_target`: выбор
  Draft-MR-флоу GitHub (`gh`) для задачи; для не-GitHub шаг пропускается.
- `orchestrator/doctor/misc_checks.py:98` — `check_base_branch`: сверка
  защиты базовой ветки идёт через API GitHub, для прочих хостингов — строка
  «сверка не реализована».
- `orchestrator/cleanup.py:304` — `cleanup_project_remote` (через
  `_forge_of`): закрытие PR проекта при уборке через `gh` только для
  GitHub. Уборка — безопасное действие, которое по требованию 2 работает
  для любой записи.

Литерал `"operator"` в `orchestrator/` встречается как актор журнала
(`store.journal(…, "operator", …)`) и как источник бюджета — это не
сравнение поля `merge_gate`, и сторож его не считает.

## Оценка объёма и деление

Сработавший сигнал: число затрагиваемых модулей/файлов зоны ≥ 5
(`targets.py`, `catalog.py`, `runner.py`, `auto.py`, `fsm.py`,
`doctor/`).

Материал для решения Оператора — обоснование монолита: каждая правка в
точках отказа — вызов одной функции `unsupported_reason` с выводом и
записью журнала (несколько строк на модуль); функция и её сторож (AC-9)
без точек отказа не закрывают п. 8 ADR-0029 — пульт по-прежнему мержил бы
сам проект `target-human`, а точки отказа без функции не мержимы вовсе.
Нарезка «функция + `doctor`» / «точки отказа» возможна, но каждая часть
несёт свои шаги ролей (~$15–20) при общем объёме правки в десятки строк.
Рамка Оператора в ТЗ — $15; `budget_usd` поставлен на планку $25
(`config.BUDGET_CALIBRATION_FLOOR_USD`) — ниже ориентира калибровки по
числу файлов зоны. Бюджет $25 принят Оператором на гейте SPEC 26.10.2026
(порог калибровки).

## Не входит

- Адаптер GitLab (задача А1).
- Исполнение `merge_gate: target-human` (задача Б2).
- Поля ветки и коммитов (задача Б1).
- Отказ на загрузке и проверке записи (`targets.target`, проверка
  `targets.py:622-628`) — запись по-прежнему принимает оба значения. Отказ
  на действиях вместо отказа на загрузке записи — реализация п. 8 ADR-0029
  по решению Оператора в ТЗ (принято на гейте SPEC 26.10.2026); текст
  ADR-0029 в этой задаче не правится.
- Правка модулей `orchestrator/` вне зон задачи — сторож AC-9 их только
  читает.
- Переписывание существующих сравнений `forge` с `"github"` вне проверки
  поддержки (раздел «Исключения сторожа AC-9»).
- Правка `orchestrator/github_adapter.py`, `orchestrator/ci.py`,
  `orchestrator/fsm_merge_gate.py`, `orchestrator/cleanup.py`,
  `docs/adr/0029-external-delivery-via-mr.md`,
  `docs/adr/0003-target-projects.md` — только чтение.
- Правка существующих тестов: ожидается, что не нужна; если окажется
  нужна — только по мандату Оператора 26.10 через гейт SPEC (без
  ослабления, с матрицей). Полный зелёный набор `tests/` — её держит пульт.

## Материалы

- `docs/adr/0029-external-delivery-via-mr.md`, п. 8.
- `tasks/01M5W27CY7K7NR9347NKD8F0NX/TZ.md`.
