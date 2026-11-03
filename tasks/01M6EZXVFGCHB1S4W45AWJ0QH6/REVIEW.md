---
task: 01M6EZXVFGCHB1S4W45AWJ0QH6
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: GitLab Б2.3-2: хук pre-push в клоне, его строка doctor, клон подмодулей и сверки перед отправкой

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–14 разнесены по шагам 1–6.
- Шаги проверяемые, по размеру MR; подход (отдельный каталог хуков,
  файл политики в `--git-common-dir`, `-c core.hooksPath` в `_push_plan`,
  сверка `host` в помощнике через `ARTEL_HOSTING_HOST`) с архитектурой не
  конфликтует. Литералов `merge_gate`/`forge` вне `targets.py` нет:
  признак берётся из `targets.merged_by_project_people`
  (`gitcmd.project_hooks_path`, `workspace.is_target_human`).
- «Влияние на систему» сходится с diff: 8 файлов, прежние
  `scripts/git-hooks/pre-push`/`pre-commit` не тронуты, путь отката описан.
- Замечание по плану одно, оно же R1-F1: шаг 6 заводит в `tests/` только
  юнит-тесты хука, помощника и двух сверок, а долгоживущих сторожей
  остальных требований в плане нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `workspace.ensure_clone` (после клона: `set_clone_hooks(clone, target)` + `write_push_policy`); `doctor --fix` — `_fix_push_hook_clone`. Остальные клоны получают `hooks_path()`. Долгоживущего сторожа в `tests/` нет — R1-F1 |
| 2 | OK | `scripts/git-hooks/target-human/pre-commit` повторяет прежний хук. Сторожа в `tests/` нет — R1-F1 |
| 3 | OK | Хук: `"$artifacts_prefix"?*` проходит (в том числе удаление); всё вне `refs/heads/*` получает отказ; удаление ветки, base и ветка не по шаблону получают отказ. Образец `case` собран с экранированием |
| 4 | OK | Отказ, когда файла нет, когда он не читается, когда нет ключа или значение пустое; в тексте отказа назван `$policy`. Только sh и `git rev-parse` |
| 5 | OK | Постоянный `core.hooksPath` клона; маркер `ARTEL_PULT_GIT` хук не читает |
| 6 | OK | `gitcmd.py:1126-1130`: `-c` идёт после сверок, рядом с `PUSH_RESET_CONFIG`, только при `merged_by_project_people`. Временная мутация показала, что в `tests/` эту вставку никто не сторожит, — R1-F1 |
| 7 | OK | Прежние файлы хуков не изменены |
| 8 | OK | Строка `clone-push-hook` (`_check_push_hook_clones`) сверяет: сумму и бит исполнения обоих хуков в каталоге действующего `core.hooksPath`, файл политики, `core.hooksPath` клона, `config.worktree` рабочих копий. `skip` по ANSWER-1 п. 5. Починка — `_fix_push_hook_clone`. В `tests/` строку не проверяет ни один тест — R1-F1 |
| 9 | OK | Клоны `target-human` исключены из `clone-hooks` (`git_hooks.py:163-165`), для прочих — по-прежнему `warn` |
| 10 | OK | `clone` входит в `HOSTING_SUBCOMMANDS`; `_clone_project` находит проект по адресу (только при `token_slot`); `submodule update` — хостинговый вызов через `in_repo`. Ограничение ANSWER-1 п. 3 учтено (`target != DEFAULT_TARGET`, `token_slot`, `.gitmodules`). В `tests/` проверен только разбор `_clone_project`; что сам клон и подмодули идут с токеном, не сторожится — R1-F1 |
| 11 | OK | Помощник читает `host=` из stdin и сравнивает с `ARTEL_HOSTING_HOST`; `url_host` по ANSWER-1 п. 2. Тест `test_appends_after_existing_git_config_entries` зелёный без правки |
| 12 | OK | `GIT_TRANSPORT_ENV_NAMES` и `_config_redirect_refusal` (`remote.origin.url`, `insteadOf`/`pushInsteadOf`/`sshCommand`, `core.hooksPath` задан и чужой). Прежние отказы на месте. В `tests/` из новых сверок проверены только `pushInsteadOf` в глобальном слое и `core.hooksPath`; переменные окружения, `remote.origin.url`, `insteadOf` и `sshCommand` не проверены — R1-F1 |
| 13 | OK | Литералов нет, `EXEMPT` не тронут |
| 14 | OK | `-c` и новые сверки только под белым списком или у `target-human`; тесты артели и `operator` зелёные |

## Замечания
- major — `tests/` (шаг 6 PLAN; планка `acceptance_tests/*.py:3` — все
  четыре файла «Группа: разовый») — свойства, которые обязаны держаться и
  после мержа (ADR-0018 п. 3), закрыты только разовой планкой. После
  мержа её не гоняет ни CI, ни гейт, поэтому регресс пройдёт молча.
  Доказательство: временная мутация `gitcmd.py:1126` (`if False and
  whitelisted …`, то есть `-c core.hooksPath` пропал) —
  `tests/test_push_hook_units.py`, `test_gitcmd_push_point.py`, оба
  MR-стенда, `test_hosting_token_units.py`: 131 passed, код возвращён.
  `grep` по `tests/` на `clone-push-hook`, `GIT_SSH_COMMAND`,
  `write_push_policy`, `_clone_submodules`, `TARGET_HUMAN_HOOKS`,
  `target-human/pre-commit` ничего не находит. Без сторожа в `tests/`
  остаются:
  1. вставка `-c core.hooksPath=<каталог>` в argv отправки `target-human`
     и её отсутствие у `operator` и артели (треб. 6, `gitcmd.py:1126-1130`);
  2. строка `clone-push-hook`: `fail` на изменённый хук, хук без бита
     исполнения, изменённый или удалённый файл политики, чужой, прежний
     или снятый `core.hooksPath` клона, `core.hooksPath` в
     `config.worktree`; `ok` после `--fix`; `skip` по ANSWER-1 п. 5; строки
     нет, если нет клонов (треб. 8, `doctor/git_hooks.py:186-354`).
     Сюда же исключение клонов `target-human` из `clone-hooks` (треб. 9);
  3. отказы по `GIT_SSH_COMMAND`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`
     (`gitcmd.py:748`), по несовпадению `remote.origin.url`, по
     `url.*.insteadOf` и `core.sshCommand` (`gitcmd.py:821-827`, треб. 12);
  4. `ensure_clone` у `target-human`: `core.hooksPath` указывает на каталог
     проекта и записан эталон политики; клоны прочих проектов получают
     прежний путь (треб. 1, `workspace.py:206-212`). `pre-commit` каталога
     `target-human` отказывает коммиту в `main` (треб. 2);
  5. отказ хука на `refs/tags/*` и `refs/notes/*` при исправном файле
     политики, когда файла нет или он не читается (треб. 3–4).
     `test_policy_without_key…` отправляет тег, но отказ там вызывает
     нехватка ключа, не правило ссылок;
  6. клон и `submodule update` проекта со `token_slot` идут с токеном
     слота, у записи без слота — без токена (треб. 10,
     `gitcmd.py:131-135`, `workspace.py:146-156`).

  Предложение: добавить в `tests/` (например, в
  `tests/test_push_hook_units.py` или в отдельный файл модуля doctor)
  тесты пунктов 1–6. У каждого — заявка «Ловит мутацию: …» с
  наблюдаемым расхождением. Можно взять стенды планки как образец, но
  не копировать файлы планки.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/ (гейт PLAN шаг 6); orchestrator/gitcmd.py:1126-1130, :748, :821-827; orchestrator/doctor/git_hooks.py:186-354; orchestrator/workspace.py:146-156, :206-212; scripts/git-hooks/target-human/* | Долгоживущие свойства требований 1, 2, 3–4 (теги, notes, состояния файла политики), 6, 8–10, 12 (переменные окружения, `remote.origin.url`, `insteadOf`, `sshCommand`) сторожит только разовая планка | После мержа регресс этих правил (подтверждено мутацией: убранный `-c core.hooksPath` — 131 passed) не ловит ни CI, ни гейт: второй рубеж белого списка может молча исчезнуть | Добавить в `tests/` тесты пунктов 1–6 из «Замечаний» с заявками «Ловит мутацию» |

## Вердикт
changes_requested. Нужно закрыть R1-F1: добавить в `tests/` долгоживущих
сторожей по пунктам 1–6. К функциональности по SPEC замечаний нет:
требования 1–14 реализованы, планка зелёная.

## Проверено исполнением
- `python3 …/artel.py plank-run 01M6EZXVFGCHB1S4W45AWJ0QH6` — 68 passed,
  код выхода pytest 0.
- `python3 -m pytest -p no:cacheprovider tests/test_push_hook_units.py
  tests/test_git_hooks.py tests/test_hosting_token_units.py
  tests/test_gitcmd_push_point.py` — 76 passed.
- Временная мутация `orchestrator/gitcmd.py:1126` (`if False and
  whitelisted and …`), прогон `tests/test_push_hook_units.py
  tests/test_gitcmd_push_point.py
  tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py
  tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py
  tests/test_hosting_token_units.py` — 131 passed, 20 subtests passed:
  мутация выжила. Код возвращён, `git status --short` чист.
- `grep -rln` по `tests/` на имена новых механизмов (`clone-push-hook`,
  `GIT_SSH_COMMAND`, `write_push_policy`, `_clone_submodules`,
  `TARGET_HUMAN_HOOKS`, `target-human/pre-commit`) — совпадений нет.
- Правка MR-стендов (только `url:` записи) проверена: утверждения вида
  `/projects/grp%2F<имя>` — строки отказа поддельного forge, а не разбор
  `url` через `gitlab_adapter._address`. Сужения данных под утверждением
  нет; правка покрыта ANSWER-1 п. 1.

## Предложения системе
- Планка задачи, где проверяется код (хук, строка doctor, сверки gitcmd),
  целиком помечена «Группа: разовый». Граница групп
  (skills/test-authoring.md) у автора планки не сработала, и в итоге
  сторожа после мержа должен дописывать разработчик. Стоит проверять
  разметку групп на гейте планки.
