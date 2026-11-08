---
task: 01M6TT4FKD1JWSJFVJ7328K03Y
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Источник отчёта базы для гейта исходов full_suite ci: поле ci_base компонента (main | branch)

## Фаза A: план

- Таблица покрытия полна (требования 1–9 → шаги 1–5); шаги размера MR.
- Подход не конфликтует с архитектурой: отправка через единую точку
  `gitcmd.in_repo` → `_push_plan`, свой неблокирующий `flock`
  (`PROJECTS/<проект>/ci_base.lock`), а не `merge_lock` (записка 2
  возврата 3), очередь — `store.steps_of_action` без правки `store.py`.
- Дефект плана: утверждение «своих тестов сверх них не добавляю — свойств
  диффа вне их охвата нет» неверно. AC-10…AC-12 закрыты только планкой,
  а она помечена `Группа: разовый`. Подробно — R1-F1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets._check_ci_base` + вид полей в `_component_value_error`: обязательность ветки, ≠ `base`, не по шаблону (`branch_template_matches` — то же правило, что у хука), `push_option_error` с запретами записи, `base` = `MAIN_BRANCH`, одинаковые значения у компонентов, `ci_base*` при `full_suite: local` отказаны |
| 2 | OK, с оговоркой | `_ci_base_unfit`: отправка только при `at_point.job is None`, `--force`, `-o` из `ci_base_push_options`, без `policy.push_options`. Оговорка R1-F2: несчитанный конвейер приравнен к «задания нет» |
| 3 | OK | `_BasePending` → `BASE_PENDING_ACTION`; `verifying_gate` журналирует его рядом с `PENDING_ACTION`; потолок — прежний в `fsm_advance`, в `note` есть «нет отчёта базы: …» (AC-7 (в) зелёный) |
| 4 | OK | `early_base_push` вызывается только в `fsm_advance.tests_writing` после `set_state -> in_dev`; сбой — запись `BASE_SEND_REFUSED_ACTION`, переход не трогается |
| 5 | OK | `_ci_base_queue_holder`: последняя запись «отчёт базы: отправка» задач проекта, держит, пока задание не `running` и не завершено и запись моложе потолка; замок только на время очереди и отправки |
| 6 | OK по коду, без сторожа | Белый список: `--force` только при всех refspec в `ci_base_branch`, источник — предок свежего `fetch_ref_sha(..., tracking_refs=False)`; хук: ключ `ci_base_branch=`, проверка предка `refs/remotes/origin/<base>` идёт после отказа удаления и `base`; эталон политики пишет ключ только при `branch`. В `tests/` этого не стережёт ничто — R1-F1 |
| 7 | OK | Классификация по `_CiAttempt.pending`; `canceled` → «задание отменено» без повторной отправки; `failed` с отчётом — годная база |
| 8 | OK | На мерже (`verifying=False`) — `_Prepare` «нет отчёта базы: отчёт базы ожидается, повтори approve — …» после отправки |
| 9 | OK | `check_ci_base_branch`: защиты хостинга по маске, ключ в файле политики клона у `target-human`; `ok`/`warn` с причиной |

## Замечания

- major — `tasks/01M6TT4FKD1JWSJFVJ7328K03Y/acceptance_tests/test_ci_base_push.py:3` (`Группа: разовый`) при пустом покрытии в `tests/` — свойства безопасности, которые ослабляет эта задача, после мержа не стережёт ни один тест. Задача расширяет права отправки: принудительная отправка в ветку вне шаблона задач. Ограничения этого расширения проверены только разовой планкой (AC-10, AC-11, AC-12), а её после мержа не гоняет ни CI, ни автогейт (ADR-0018 п. 3). Без сторожа остаются все места класса:
  - `orchestrator/gitcmd.py:1008-1009, 1014-1015` — `--force` пропускается только когда все refspec идут в `ci_base_branch`;
  - `orchestrator/gitcmd.py:1045-1055` + `_ci_base_source_refusal` `:1088-1103` — источник обязан быть предком свежего `origin/<base>` (`tracking_refs=False`), а не локальной ссылки;
  - `scripts/git-hooks/target-human/pre-push:99-104` — хук пропускает в ветку отчёта базы только предка `origin/<base>`;
  - AC-12 — `kill`/уборка не удаляют `ci_base_branch`.

  Проверено временной мутацией (код возвращён, `git status` чист): в `_ci_base_source_refusal` проверку предка заменил на `if False and …`, в хуке `git merge-base --is-ancestor …` заменил на `true`. Набор `tests/test_gitcmd_push_point.py`, `tests/test_push_hook_units.py`, `tests/test_push_hook_stand.py`, `tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_doctor.py` — 84 passed, ни одного красного. Сценарий последствий: любая будущая правка `_whitelist_refusal` или хука молча снимает ограничение источника, и через `ci_base_branch` можно принудительно отправить произвольный коммит — тот самый обход правил веток задач, который ANSWER-1 (ответ 7, матрица неослабления) закрывал условием. Заявление PLAN «свойств диффа вне их охвата нет» не выдерживает проверки. Предложение: добавить в `tests/` долгоживущие тесты (например, в `tests/test_gitcmd_push_point.py` и `tests/test_push_hook_units.py` / `tests/test_push_hook_stand.py`, не повторяя файлы задачи из лока) с заявками «Ловит мутацию: …» на четыре свойства выше. Каждую заявку проверить той же временной мутацией.
- minor — `orchestrator/advance_gates/outcome_integrity.py` `_ci_base_unfit` (ветка `at_point.job is None`) и `early_base_push` (`_ci_last_attempt(...)` → `found is None`) — сбой чтения конвейера (`forge.pipeline_status` с `reason`, пустой `jobs`, например HTTP 502) считается «задания нет вовсе», и пульт делает принудительную отправку `B`. Требование 2 разрешает отправку только когда задания нет. Сценарий: API GitLab временно отдаёт 502 на конвейер `B`, у которого задание уже идёт. Если очередь пуста (первая отправка проекта или прошлая старше потолка), `B` отправляется повторно, и на ветке появляется лишний конвейер. Вреда гейту нет, только лишний прогон CI. Предложение: при `res.reason` у `_ci_last_attempt` не отправлять, а ждать — проходящая негодность «статус не прочитан».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/gitcmd.py:1008-1015, :1045-1055, :1088-1103; scripts/git-hooks/target-human/pre-push:99-104; AC-12 (kill/уборка) | Расширение прав отправки (force и источник-предок свежего `origin/<base>` в белом списке и хуке, неудаление `ci_base_branch`) закрыто только планкой `Группа: разовый`; в `tests/` сторожа нет (временная мутация обеих проверок предка — `tests/` зелёные) | После мержа правка белого списка или хука молча снимает ограничение источника, и через `ci_base_branch` можно принудительно отправить произвольный коммит | Добавить долгоживущие тесты в `tests/` с заявками «Ловит мутацию» на четыре свойства; проверить временной мутацией |
| R1-F2 | open | orchestrator/advance_gates/outcome_integrity.py (`_ci_base_unfit`, `early_base_push`) | Сбой чтения конвейера (`pipeline_status.reason`) приравнен к «задания нет» — отправка | Лишний конвейер CI на `ci_base_branch` при временном сбое API | При `reason` не отправлять, ждать как проходящую негодность |

## Вердикт

changes_requested. Исправить R1-F1: долгоживущие тесты в `tests/` на ограничения отправки в `ci_base_branch` в белом списке и хуке, а также на неудаление ветки. R1-F2 (minor) — по желанию, но со статусом в реестре.

Наблюдение для Оператора: планка `acceptance_tests/test_ci_base_push.py` помечена `Группа: разовый`, хотя проверяет свойства кода (AC-10, AC-11 — правила белого списка и хука; AC-12). По ADR-0020 это свойство кода под разовой меткой. Планка залочена: её группу может сменить только `amend-tests`, поэтому замечание разработчику — о сторожах в `tests/`, не о планке.

## Проверено исполнением

- `python3 …/artel.py plank-run 01M6TT4FKD1JWSJFVJ7328K03Y` — 17 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_doctor.py tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_fields.py tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_gate.py tests/test_push_hook_units.py` — 58 passed, 14 subtests passed (141.8 с).
- Временная мутация (R1-F1): в `orchestrator/gitcmd.py::_ci_base_source_refusal` проверка предка заменена на `if False and …`, в хуке `pre-push` `git merge-base --is-ancestor` заменён на `true`. Затем `python3 -m pytest -q tests/test_gitcmd_push_point.py tests/test_push_hook_units.py tests/test_push_hook_stand.py tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_doctor.py` — 84 passed, ни одного красного. Код возвращён, `git status --porcelain` пуст.

## Предложения системе

- Задача, которая расширяет правила белого списка или хука отправки, получила планку `Группа: разовый` на эти правила, а разработчик не добавил сторожей в `tests/`. Стоит, чтобы `skills/test-authoring.md` прямо называл правила белого списка и хуков отправки долгоживущими свойствами.
