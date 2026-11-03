---
task: 01M6EZXVFGCHB1S4W45AWJ0QH6
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: GitLab Б2.3-2: хук pre-push в клоне, его строка doctor, клон подмодулей и сверки перед отправкой

## Фаза A — план
- В PLAN добавлен шаг 7: долгоживущие сторожа в `tests/` под R1-F1. Таблица
  покрытия обновлена, в ней есть все требования 1–14. Шаги проверяемые.
- «Влияние на систему» сходится с diff. Инкрементальный diff итерации 2
  трогает только `tests/test_push_hook_stand.py` (новый) и
  `tests/test_push_hook_units.py` (+2 метода). Код не менялся, прежние
  утверждения не тронуты, удалённых строк нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Сторож — `test_ensure_clone_human_gets_own_hooks_and_policy_others_old_path` (каталог `target-human`, эталон политики побайтно; у `operator` прежний путь и файла политики нет); `--fix` — `test_push_hook_line_fails_on_damage_and_fix_restores` |
| 2 | OK | `test_human_pre_commit_refuses_main_commit_without_marker` |
| 3 | OK | `test_tags_and_notes_refused_with_valid_policy`, вместе с прежними юнит-тестами хука. Мутация «всё вне `refs/heads/*` пропускается» дала 3 красных |
| 4 | OK | `test_missing_or_unreadable_policy_refuses_naming_path`, прежний тест на пустой/отсутствующий ключ |
| 5 | OK | Без изменений с итерации 1 (постоянный `core.hooksPath`, хук не читает маркер) |
| 6 | OK | `test_human_push_carries_hooks_path_operator_does_not`. Мутация прошлой итерации `gitcmd.py:1126` теперь красная |
| 7 | OK | Прежние файлы хуков не тронуты |
| 8 | OK | 7 повреждений → `fail`, потом `--fix` → `ok`; `config.worktree` с значением в detail; `skip` без хука в `HEAD`. Мутация «бит исполнения не сверяется» красная |
| 9 | OK | `test_push_hook_line_skip_without_reference_and_absent_without_clones`: `clone-hooks` остаётся `warn` для `operator`, `target-human` из него исключён |
| 10 | OK | `test_clone_and_submodules_carry_slot_token`, `test_clone_without_slot_goes_without_token`. Мутация «`submodule update` мимо `gitcmd`» красная |
| 11 | OK | Без изменений с итерации 1, юнит-тесты помощника на месте |
| 12 | OK | Тесты `test_transport_env_refuses_before_git` ×3 и `test_config_redirect_refuses_before_git` ×3. Мутации «нет `GIT_SSH_COMMAND`» и «нет `insteadOf`/`sshCommand` в `PUSH_REDIRECT_CONFIG`» красные |
| 13 | OK | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` (сторож ac9) зелёный, `EXEMPT` не тронут |
| 14 | OK | Тесты артели и `operator` из пакета зелёные |

## Замечания
Нет blocker/major. Заявки «Ловит мутацию» у всех 19 новых методов говорят
о наблюдаемом расхождении (отказ или его отсутствие, статус строки, argv,
окружение вызова). Выборочно проверил 6 заявок временной мутацией (см.
ниже), все тесты покраснели.

Наблюдение без замечания (minor, на вкус): бит исполнения проверяется
только у `pre-commit` (`pre-commit-exec`), содержимое — только у
`pre-push` (`pre-push-text`). Сверка общая и идёт циклом по обоим файлам
(`doctor/git_hooks.py:219-232`), поэтому одного варианта на каждый тип
расхождения хватает.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/ (гейт PLAN шаг 6); orchestrator/gitcmd.py:1126-1130, :748, :821-827; orchestrator/doctor/git_hooks.py:186-354; orchestrator/workspace.py:146-156, :206-212; scripts/git-hooks/target-human/* | Долгоживущие свойства требований 1, 2, 3–4, 6, 8–10, 12 сторожила только разовая планка | После мержа регресс второго рубежа никто бы не поймал | Принято (итерация 2): `tests/test_push_hook_stand.py` (17 методов, стенд `real_git`) и 2 метода в `tests/test_push_hook_units.py` покрывают пункты 1–6. Временные мутации ревьювера по пунктам 1, 2, 3, 5, 6 красные (см. «Проверено исполнением») |

## Вердикт
approved. R1-F1 закрыто: долгоживущие сторожа добавлены, и проверка
мутациями показала, что они ловят то, что заявлено. Требования 1–14
реализованы, планка зелёная, CI коммита 8e9cf85c зелёный.

## Проверено исполнением
- `python3 -m pytest -p no:cacheprovider -q tests/test_push_hook_stand.py
  tests/test_push_hook_units.py` — 32 passed, 14 subtests passed.
- `python3 -m pytest -p no:cacheprovider -q tests/test_push_hook_stand.py
  tests/test_push_hook_units.py tests/test_git_hooks.py
  tests/test_hosting_token_units.py tests/test_gitcmd_push_point.py` — 98
  passed, 25 subtests passed.
- `python3 -m pytest -q tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`
  (сторож ac9, требование 13) — 16 passed.
- `artel.py plank-run 01M6EZXVFGCHB1S4W45AWJ0QH6` — 68 passed, код выхода
  pytest 0.
- Временные мутации. После каждой код возвращён `git checkout --`,
  `git status --short` чист:
  1. `gitcmd.py:1126` `if False and whitelisted …` (без `-c core.hooksPath`),
     вместе с `GIT_TRANSPORT_ENV_NAMES` без `GIT_SSH_COMMAND` и
     `PUSH_REDIRECT_CONFIG` только с `pushinsteadof`. Прогон
     `tests/test_push_hook_stand.py`: 4 failed —
     `test_human_push_carries_hooks_path_operator_does_not`,
     `test_transport_env_refuses_before_git[GIT_SSH_COMMAND]`,
     `test_config_redirect_refuses_before_git[insteadOf]`,
     `[sshCommand]`.
  2. `doctor/git_hooks.py:230` — без сверки бита исполнения; `workspace.py:152`
     — `submodule update` прямым `subprocess.run` мимо `gitcmd`. Прогон
     `tests/test_push_hook_stand.py`: 2 failed — `…[pre-commit-exec]`,
     `test_clone_and_submodules_carry_slot_token`.
  3. `scripts/git-hooks/target-human/pre-push:85` — `continue` вместо
     отказа ссылке вне `refs/heads/*`. Прогон `tests/test_push_hook_units.py`:
     3 failed — `refs/tags/v1`, `refs/notes/x`, `refs/artifacts/` (пустой
     id).

## Предложения системе
- Пакет ревью итерации 2 содержит только инкрементальный diff `tests/`.
  Чтобы мутировать код, ревьюверу приходится читать его адресно по
  номерам строк из прошлого REVIEW. Это работает, пока код между
  итерациями не менялся. Полезно, если пакет будет отмечать «код с
  прошлого вердикта не менялся» явно.
