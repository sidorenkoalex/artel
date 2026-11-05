---
task: 01M6N7CYKDAMAKENX60CBK7VQX
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "б) мандат в ANSWER: Ослабление тестов разрешено: tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py / Ослабление тестов разрешено: tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py / Ослабление тестов разрешено: tests/test_epic_draft_promote_unsupported_project.py; в) пути-признаки (тесты): tests/, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py, tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py, tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py, tests/test_awaiting_human_units.py, tests/test_epic_draft_promote_unsupported_project.py, tests/test_gitcmd_push_point.py, tests/test_mr_delivery_units.py, tests/test_push_hook_stand.py; в) пути-признаки (гейты): orchestrator/fsm_merge_gate.py; в) защищённые пути: .github/, .github/workflows/, .github/workflows/ci.yml; г) budget_usd 85 ≥ 45; д) ТЗ ссылается на ADR: ADR-0029."
spec_sha: 17645f1c02924be296d02106b43782d402ea4c9e
schema_version: 5
---

# SPEC-AUDIT: Ручной мерж для GitHub, часть 2: открытие пары github + target-human, проверки записи и строки doctor

Пятый визит аудита. Сравнил эту версию SPEC с прошлой (d4d80912) по
диффу автокоммитов `64caf2988..08d4b302c` ссылки документов. Изменились
три места, все переносят решение Оператора №3 с гейта SPEC:
- AC-1 — добавлено условие про remote `origin` подготовленного клона
  (решение №3.2);
- AC-9 — до отправки ветка задачи заранее заводится в голом `origin`, и
  проверяется, что `kill` её удалил (решение №3.1);
- «Материалы» — добавлена записка решения №3.3, адреса к AC-9 и AC-1.

Прочий текст SPEC совпадает с версией d4d80912. Её разбор по всем разделам
(прошлый визит, verdict pass) остаётся в силе и ниже не повторяется: здесь
только то, что затронули правки.

## ТЗ и SPEC

- Решения №3.1 и №3.2 перенесены в AC-9 и AC-1 дословно.
- Решение №3.3 перенесено в «Материалы» как записка, проверку тестов оно
  не меняет.
- Новые формулировки не противоречат требованию 9 SPEC («до отправки
  удаляется только ветка origin задачи, если она есть»). Они усиливают
  только то, как это проверяется. С ТЗ (требование 9, критерий о `kill`) и
  с прежними решениями №1.x и №2.x противоречий нет.

## Факты против кода

Подтверждено (HEAD ветки 2b62f8a03 не менялся):
- `orchestrator/cleanup.py:313` — `notes.append(_delete_origin_branch(workspace.task_repo(task_id), branch))`
  в пути уборки до отправки;
- `orchestrator/cleanup.py:273` — текст `f"ветка origin {branch}: удалена"`;
- `orchestrator/cleanup.py:311-312` — закрытие PR литералом
  `_forge_of(target) == "github"`;
- `orchestrator/cleanup.py:295-301` — ранний выход «сервер проекта не
  тронут…» после отправки;
- `tests/sandbox.py:969` — `_is_local_git_address` возвращает `True` для
  всего, что не `file://`, не путь и не http(s). Голое имя remote
  считается локальным без проверки его адреса, так что условие AC-1 о
  remote по имени обосновано.

Не подтверждено:
- Записка решения №3.3 в «Материалах» говорит: «относительно 2b62f8a03
  изменился только `orchestrator/reporters/outcome.py`». На деле
  `git diff --stat 2b62f8a03 77e9ca9c` показывает шесть файлов:
  - `orchestrator/reporters/outcome.py`;
  - `docs/codebase-map.md` (файл зоны SPEC);
  - два новых теста в `tests/` (зона SPEC):
    `tests/test_01m6mzaeg0m8q2gpbx4rsak71z_junit_hidden_dir.py`,
    `tests/test_01m6mzaeg0m8q2gpbx4rsak71z_junit_prior_parse.py`;
  - `docs/adr/0023-role-step-sandbox.md`;
  - `docs/backlog.md`.

  Вывод записки при этом верен: файлы, на строки которых ссылается SPEC
  (`orchestrator/` кроме `reporters/outcome.py`, перечисленные тесты),
  не менялись, номера строк SPEC верны. Утверждение «дифф в зонах SPEC
  пуст» ложно только для `docs/codebase-map.md` и новых файлов `tests/`.
  Для разработчика это значит: при подтяжке main карта разойдётся, и её
  нужно регенерировать (conventions-core, «Git»). На критерии это не
  влияет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | Как в прошлом визите. Новое условие: подготовленный клон без remote или с локальным `origin` (образец `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:176` создаёт только `.git`, и `git remote get-url origin` падает — remote нет). Тест, оставивший `origin` на `https://localhost/…`, нарушает критерий: сетевую команду по имени `origin` ловит шпион. До кода тест красный отказом поддержки и безопасен |
| AC-2…AC-8 | да | без изменений с прошлого визита |
| AC-9 | да | Мутации, которые ловит тест: (1) `_close_project_pr` до отправки для `target-human` — шпион `gh`; (2) пропуск `_delete_origin_branch` для проекта людей — ветка останется в голом `origin`, в журнале не будет «удалена»; (3) «PR не тронут» только в одной из веток пути; (4) потеря прежнего текста после отправки. Прежнюю дыру («если она есть» — тест без ветки в `origin`) новая формулировка закрыла. До кода красная фаза зовёт `ci.gh pr close`: подделка обязательна по разделу безопасности ТЗ. `push --delete` идёт в локальный голый `origin`, это не сеть (`tests/sandbox.py:964`) |
| AC-10…AC-13 | да | без изменений с прошлого визита |

## Зоны

Без изменений с прошлого визита. Правки AC-9 и AC-1 укладываются в
`orchestrator/cleanup.py` и `tests/`. Защищённые пути не затронуты.

## Матрица неослабления

Строки прошлого визита в силе, новых свойств правки не трогают.

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `kill` до отправки, `github` + `target-human` | закрытие PR и удаление ветки origin (`orchestrator/cleanup.py:311-313`) | закрытие PR — нет (решение 04.11 п. 3); удаление ветки — да | AC-9 (теперь с заведённой веткой в `origin`), AC-10 | ок |

## Пути обхода гейтов

Новых путей не нашёл. Решение №3.1 закрыло обход AC-9 «тест без ветки в
`origin`». Решение №3.2 закрыло обход AC-1 «сетевая команда по имени
remote с http-адресом».

## Вердикт

concerns: одно мелкое отклонение, его может решить Оператор на гейте.

1. В записке решения №3.3 («Материалы» SPEC, последний абзац перед
   «Безопасность тестов») ложный факт: «относительно 2b62f8a03 изменился
   только `orchestrator/reporters/outcome.py`». На самом деле
   `2b62f8a03..77e9ca9c` меняет ещё `docs/codebase-map.md` (зона SPEC), два
   новых файла `tests/` (зона SPEC), `docs/adr/0023-role-step-sandbox.md` и
   `docs/backlog.md`. Вывод «номера строк SPEC верны» при этом верен:
   файлы, на строки которых ссылается SPEC, не менялись. Последствие —
   карту после подтяжки main нужно регенерировать. Критерии от этого не
   меняются.

Остальное подтверждено кодом:
- правки AC-1 и AC-9 (`orchestrator/cleanup.py:273`, `:313`;
  `tests/sandbox.py:969`);
- прошлый разбор версии d4d80912.
