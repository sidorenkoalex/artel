---
task: 01M6EZXVFGCHB1S4W45AWJ0QH6
type: review
author_role: reviewer
status: changes_requested
iteration: 3
schema_version: 5
---

# REVIEW: GitLab Б2.3-2: хук pre-push в клоне, его строка doctor, клон подмодулей и сверки перед отправкой

## Фаза A — план
- Шаг 8 (возврат из merge_gate) — проверяемая единица: в нём четыре пункта
  возврата и 10 тестов. Таблица покрытия дополнена (требования 4 и 12 → шаг 8).
- Толкование «отсутствия» файла политики (пульт пишет эталон перед каждой
  отправкой) расходится с буквой требования 1: там названы ровно два
  случая записи. Обоснование в PLAN выдерживает проверку. Хук по-прежнему
  отказывает отправкам роли из оболочки без файла (требование 4 держится).
  Отправка пульта и так проходит сверки `gitcmd`. Поэтому замечанием это
  не ставлю.
- «Влияние на систему» и «Риски» называют новый побочный эффект: отправка
  пишет файл в `.git` клона. Не названо, что запись идёт по пути, который
  контролирует роль (см. R3-F1).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 2. Эталон и путь перенесены в `gitcmd`, `workspace` их делегирует (`workspace.py:108-120`) |
| 2 | OK | Без изменений |
| 3 | OK | Без изменений |
| 4 | OK с замечанием | `_push_policy_refusal` (`gitcmd.py:318-339`) отказывает до git, если файл нельзя записать или прочитать, и называет путь. Но запись идёт по символической ссылке — R3-F1 |
| 5 | OK | Без изменений |
| 6 | OK | Без изменений |
| 7 | OK | Прежние хуки не тронуты |
| 8 | OK | Без изменений с итерации 2. Символическая ссылка вместо файла политики строкой не ловится, потому что сумма считается по цели ссылки (часть R3-F1) |
| 9 | OK | Без изменений |
| 10 | OK | Без изменений |
| 11 | OK | Без изменений |
| 12 | OK | `--get-all remote.origin.url` и ровно одно значение (`gitcmd.py:903-911`). `_strict_config` отказывает при сбое чтения (`:512-528`, `:881-889`). `GIT_SSH` в `GIT_TRANSPORT_ENV_NAMES` (`:249`). Сторожа: `test_second_origin_url_refuses_before_git[local/global]`, `test_config_read_failure_refuses_before_git` ×3, `test_git_ssh_env_refuses_before_git` |
| 13 | OK | Признак проекта — `targets.merged_by_project_people` (`gitcmd.py:1181`), литералов нет |
| 14 | OK | Строгое чтение псевдонима (`gitcmd.py:1154-1159`) стоит после выхода для проектов не под белым списком (`:1145-1146`). У артели и `operator` вызов прежний |

## Замечания
- major — `orchestrator/gitcmd.py:330` (`_push_policy_refusal`, `path.write_bytes(expected)`).
  Тот же класс есть и в `orchestrator/workspace.py:134` (`write_push_policy`:
  `ensure_clone` и `doctor --fix`). Пульт пишет файл политики по пути в общем
  каталоге git клона и идёт по символической ссылке. Этот каталог под
  контролем роли (модель угроз SPEC: роль меняет конфигурацию клона и
  рабочей копии). Сценарий: роль кладёт
  `<клон>/.git/artel-push-policy` → символическую ссылку на любой файл,
  куда может писать процесс пульта (исходник пульта в `config.ROOT`, БД
  `store`, файл в `~` Оператора). Следующая отправка пульта из этого клона
  затирает цель ссылки четырьмя строками политики. Чтение обратно
  проходит через ту же ссылку и даёт эталон, поэтому отказа нет, отправка
  идёт дальше. Строка `doctor` `clone-push-hook` тоже видит эталон
  (сумма по цели) и не отличает такое состояние от исправного.
  Пробой подтверждено: временный репозиторий, ссылка на файл `victim`,
  `_push_policy_refusal(...)` вернул `None`, `victim` стал текстом
  политики. До итерации 3 такая запись шла только при `ensure_clone`
  (свежий клон, ссылки там ещё нет) и при `doctor --fix`, который
  запускает Оператор. Теперь её вызывает любая отправка пульта, а условия
  создаёт роль.
  Предложение: в обоих местах не идти по ссылке. Например, открывать с
  `os.O_NOFOLLOW` (или проверить `path.is_symlink()`/`lstat` и отказать с
  путём файла), либо писать во временный файл того же каталога и
  `os.replace` — это заменяет саму ссылку, а не её цель. Строке `doctor`
  считать символическую ссылку на месте файла политики расхождением
  `fail`, а `--fix` — заменять её обычным файлом. Нужен тест в
  `tests/test_push_hook_stand.py`: ссылка на месте файла политики даёт
  отказ (или замену ссылки), а цель ссылки после отправки не изменилась.
- minor — `orchestrator/gitcmd.py:1184` — `deleting ="--delete" …`:
  случайно потерян пробел перед `"`, правка вне смысла итерации. Вернуть
  `deleting = "--delete"`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R3-F1 | fixed — `gitcmd.write_push_policy_file`: временный файл того же каталога (`mkstemp`, `O_EXCL`) + `os.replace` — заменяется сама ссылка, цель не трогается; им пишут `_push_policy_refusal` и `workspace.write_push_policy` (`ensure_clone`, `doctor --fix`). `clone-push-hook`: ссылка на месте файла политики — `fail` с целью ссылки, `--fix` заменяет её обычным файлом. Тесты `test_push_replaces_policy_symlink_not_its_target`, `test_write_push_policy_replaces_symlink_not_its_target`, `test_push_hook_line_fails_on_policy_symlink_and_fix_replaces` | orchestrator/gitcmd.py:330; orchestrator/workspace.py:134; orchestrator/doctor/git_hooks.py (сверка файла политики) | Запись файла политики идёт по символической ссылке в общем каталоге git клона, а этот каталог контролирует роль | Роль заставляет пульт затереть любой файл, куда он может писать (исходник пульта, БД, файлы Оператора), и отправка при этом проходит; `doctor` подмену не видит | Не идти по ссылке (`O_NOFOLLOW` / `lstat` → отказ, либо временный файл + `os.replace`); `doctor` — `fail` на ссылке, `--fix` — заменить её обычным файлом; тест в `tests/test_push_hook_stand.py` |
| R3-F2 | fixed — пробел возвращён: `deleting = "--delete"` | orchestrator/gitcmd.py:1184 | `deleting ="--delete"` — потерян пробел | Только стиль | Вернуть пробел |

## Вердикт
changes_requested: R3-F1 (major, безопасность) и R3-F2 (minor). Остальные
пункты возврата из merge_gate закрыты: несколько значений
`remote.origin.url`, строгое чтение конфигурации, `GIT_SSH`, перезапись
политики перед отправкой. Сторожа проверены мутациями.

## Проверено исполнением
- `python3 -m pytest -p no:cacheprovider -q tests/test_push_hook_stand.py
  tests/test_push_hook_units.py tests/test_gitcmd_push_point.py
  tests/test_git_hooks.py tests/test_hosting_token_units.py` — 108 passed,
  25 subtests passed.
- `artel.py plank-run 01M6EZXVFGCHB1S4W45AWJ0QH6` — 68 passed, код выхода
  pytest 0.
- Пробой R3-F1 (скрипт во временном каталоге, после прогона удалён): `git init`, затем
  `.git/artel-push-policy` → ссылка на `victim`,
  `gitcmd._push_policy_refusal("p", {"base": "main"}, repo)` → `None`;
  содержимое `victim` после вызова —
  `project=p\nbase=main\nbranch_template=task/{id}-{slug}\nartifacts_prefix=refs/artifacts/\n`.
- Временные мутации (вместе): `gitcmd.py:903` `--get` вместо `--get-all`,
  `gitcmd.py:330` без записи политики. Прогон `tests/test_push_hook_stand.py`:
  4 failed — `test_second_origin_url_refuses_before_git[local]`, `[global]`,
  `test_push_rewrites_policy_from_entry[changed]`, `[deleted]`. Код
  возвращён `git checkout -- orchestrator/gitcmd.py`, `git status --short`
  чист.

## Предложения системе
- Класс «пульт пишет файл по пути в каталоге, который контролирует роль»
  (`.git` клона, рабочая копия) стоит вынести в скил ревью или в
  инвариант guard: запись без защиты от символической ссылки — это
  примитив перезаписи для роли.
