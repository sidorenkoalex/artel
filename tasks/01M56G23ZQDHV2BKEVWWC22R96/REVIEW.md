---
task: 01M56G23ZQDHV2BKEVWWC22R96
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Команда проверки артефакта для роли и миссии ролей внешнего проекта по профилю

## Фаза A: план

- Таблица покрытия PLAN полна: требования 1–11 разнесены по шагам 1–4.
- Шаги размером с MR: команда `guard`, приём долгоживущего пути в `plank-run`,
  развилка миссий. Микроопераций и шага «сделать всё» нет.
- Подход не конфликтует с архитектурой. Правило guard не копируется
  (`scripts.guard.main()` с подменой argv). Отказы до выкладки общие для обеих
  веток `plank-run`, без копии кода. Миссии артели развиваются по уже
  вычисленному `artel` (`brief.is_artel_task`).
- «Влияние на систему» сходится с diff. Затронуты ровно `artel.py`,
  `plank_run.py`, `role_prompt.py`, новый `tests/test_artel_guard_command_forms.py`
  и регенерированная карта. Защищённых путей (`skills/`, `templates/`,
  `.github/`, `gates.yaml`, `roles.yaml`) в diff нет. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/artel.py` `_cmd_guard`: зовёт `scripts.guard.main()`, своей копии правил нет. Форма `tasks/<id>/<файл>` снимается префиксом |
| 2 | OK | Абсолютные пути `artifact_branch.docs_dir(...)/<файл>` в argv, режим по файлам: `check` + `spec_path_errors` + `plan_appendix_errors`, пропуск записок и паспорта делает сам `main()`. Без файла — `docs.glob("*.md")`, только первый уровень. Код выхода — код `main()` |
| 3 | OK | Читает только `store.task_target`/`resolve_task_id` и файлы. Lease, журнала и коммитов нет. `guard` добавлена в `_ROLE_ALLOWED_COMMANDS` |
| 4 | OK | `role_prompt._guard_tool`: у внешнего проекта — `python3 <ROOT>/orchestrator/artel.py guard <id> …` для analyst, developer, spec_auditor |
| 5 | OK | `plank_run._long_lived_arg` идёт через `Profile.is_long_lived`; регэксп `guard.is_long_lived_test_path` — `fullmatch` с `[a-z0-9_]` в имени, `..` не проходит. Нет файла — именованный отказ «нет в рабочей копии кода». Дальше те же отказы до выкладки (документы, ссылка, расхождение), затем `run_plank` без выкладки, раннер профиля или пульта |
| 6 | OK | Для долгоживущего пути проверки `_has_tests` нет |
| 7 | OK | Без долгоживущего пути ветка выбора прежняя (`elif not _has_tests`, `if file_arg and not long_lived`). Выкладка и прогон планки перенесены без смены логики |
| 8 | OK | `_plank_run_point`: у внешнего проекта — `plank-run <id> <long_lived_prefix><имя>.py`, без `python3 -m pytest` и без удвоения каталога |
| 9 | OK | `_reviewer_checks_note`: у внешнего проекта — `guard`, `plank-run`, `suite-run` командами пульта, без «Права не сужены» |
| 10 | OK | Для артели тексты миссий прежние (планка AC-9 зелёная). Белый список отличается ровно на `guard` |
| 11 | OK | Тесты на песочнице, `random` с печатью зерна, pytest подменён, сети нет |

## Замечания

Блокеров и major нет. Наблюдения ниже не требуют правки, поэтому в реестр не
внесены:

- `orchestrator/artel.py` `_cmd_guard`: аргумент `<файл>` не ограничен каталогом
  документов (`guard <id> ../<другая задача>/SPEC.md` проверит чужой файл).
  Команда только читает, и роль может прочитать эти файлы и так, поэтому
  последствий нет.
- Миссии ролей внешнего проекта собирают команду через `config.ROOT` в момент
  сборки. Разрешающее правило `providers/claude.py` строится тем же способом.
  Совпадение подтверждено тестом AC-4/AC-8.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved. Все требования SPEC реализованы. Долгоживущие тесты задачи, планка и
тесты затронутых модулей зелёные. Реестр пуст.

## Проверено исполнением

- `python3 -m pytest -q -p no:cacheprovider` на 14 модулях:
  `…_role_missions`, `…_plank_run`, `…_plank_run_role`, `…_plank_run_drift`,
  `…_preflight` (01m4p4zp…), `…_note_mission`, `…_knowledge_command`
  (01m4s0k2…), `…_profile_mission`, три долгоживущих файла задачи
  (`external_missions`, `guard_command`, `plank_run_long_lived`),
  `test_artel_guard_command_forms`, `test_plank_run_edges`,
  `test_role_prompt_test_author_mission`. Итог: 84 passed, 154 subtests passed
  за 286 с.
- `artel.py plank-run 01M56G23ZQDHV2BKEVWWC22R96` (планка AC-9 артели):
  1 passed, код выхода 0.
- Временная мутация: в `plank_run._long_lived_target` убрал ветку
  `pytest-own`, то есть относительный путь с `::узлом` уходит в `run_plank`
  без перевода. `…_plank_run_long_lived.py -k ac5` дал 3 failed (подтесты
  AC-5: цель `<файл>::<тест>` и рабочий каталог). Код возвращён
  `git checkout`, `git status` чист.
- `conftest._is_targeted_path` прочитан: путь `tests/test_<id>_*.py`,
  который `plank-run` передаёт раннеру пульта, сторож роли признаёт целевым.
  Цель для артели относительная, как требует сторож.

## Предложения системе

- `acceptance.run_plank` с `pytest-own` не переводит в `workdir` узел
  `::тест` пути от корня (`_own_target(node=False)`). Обход абсолютным путём в
  `plank_run._long_lived_target` рабочий, но лучше дать `run_plank` флаг
  `node` (повторяю предложение PLAN).
