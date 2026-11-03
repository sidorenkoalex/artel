---
task: 01M6EZXVFGCHB1S4W45AWJ0QH6
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 5
---

# REVIEW: GitLab Б2.3-2: хук pre-push в клоне, его строка doctor, клон подмодулей и сверки перед отправкой

## Фаза A — план
- Шаг 9 (итерация 4) — проверяемая единица: в нём R3-F1, R3-F2 и 3 теста.
  Таблица покрытия дополнена (требования 4 и 8 → шаг 9).
- Тест `test_unusable_policy_refuses_before_git` переделан (`unreadable` →
  `unwritable-dir`). Этот тест добавлен в этой же ветке на итерации 3, в
  `main` его нет. Поэтому это не ослабление существующего теста. Нечитаемый
  файл теперь штатно заменяется через `os.replace`. Отказ хука на
  нечитаемый файл политики (требование 4) по-прежнему сторожит
  `tests/test_push_hook_units.py`.
- «Риски» описывают запись через временный файл и `os.replace`. Это
  совпадает с diff.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `workspace.write_push_policy` пишет через `gitcmd.write_push_policy_file` (`workspace.py:134-135`) |
| 2 | OK | Без изменений |
| 3 | OK | Без изменений |
| 4 | OK | `_push_policy_refusal` пишет файл без перехода по ссылке (`gitcmd.py:353`). Если запись не удалась, отказ называет путь |
| 5 | OK | Без изменений |
| 6 | OK | Без изменений |
| 7 | OK | Прежние хуки не тронуты |
| 8 | OK | Символическая ссылка на месте файла политики даёт `fail`, цель ссылки названа в detail (`doctor/git_hooks.py:284-286`). `--fix` ставит на место ссылки обычный файл |
| 9 | OK | Без изменений |
| 10 | OK | Без изменений |
| 11 | OK | Без изменений |
| 12 | OK | Без изменений с итерации 3 |
| 13 | OK | Без изменений |
| 14 | OK | Без изменений |

## Замечания
Новых замечаний нет. R3-F1 и R3-F2 закрыты, см. реестр.

Наблюдение, не замечание. `write_push_policy_file` создаёт файл в
`path.parent`, то есть в общем каталоге git, который возвращает
`rev-parse`. Если роль подменит сам `.git` (ссылкой или файлом `gitdir:`),
пульт создаст или заменит в выбранном ролью каталоге только файл с именем
`artel-push-policy`. Произвольный файл так не перезаписать, поэтому
примитива из R3-F1 нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R3-F1 | accepted | orchestrator/gitcmd.py:319-338, :353; orchestrator/workspace.py:134-135; orchestrator/doctor/git_hooks.py:284-286 | Запись файла политики шла по символической ссылке в общем каталоге git клона | Закрыто: запись идёт во временный файл (`mkstemp`) и затем `os.replace`, поэтому заменяется сама ссылка. Пробой повторён, цель ссылки не изменилась. Строка doctor даёт `fail` на ссылке, `--fix` её заменяет | Принято: три теста-сторожа проверены временной мутацией |
| R3-F2 | accepted | orchestrator/gitcmd.py:1208 | `deleting ="--delete"` — потерян пробел | Закрыто: пробел возвращён | Принято |

## Вердикт
approved. R3-F1 и R3-F2 закрыты, остальные пункты без изменений с
итерации 3. Новых blocker/major нет.

## Проверено исполнением
- `python3 -m pytest -p no:cacheprovider -q tests/test_push_hook_stand.py
  tests/test_push_hook_units.py tests/test_gitcmd_push_point.py
  tests/test_git_hooks.py tests/test_hosting_token_units.py`: 111 passed,
  25 subtests passed.
- `artel.py plank-run 01M6EZXVFGCHB1S4W45AWJ0QH6`: 68 passed, код выхода
  pytest 0.
- Повтор пробоя R3-F1. Скрипт: `git init` во временном каталоге,
  `.git/artel-push-policy` → ссылка на `victim` с текстом `SECRET\n`, затем
  `gitcmd._push_policy_refusal("p", {"base": "main"}, repo)`. Результат:
  вызов вернул `None`; `victim` остался `SECRET\n`; на месте ссылки обычный
  файл с эталоном политики; временных `.artel-push-policy.*` нет. Скрипт
  после прогона удалён.
- Временные мутации (вместе): тело `write_push_policy_file` заменено на
  `path.write_bytes(data)`, сверка `path.is_symlink()` в
  `doctor/git_hooks.py` заменена на `False`. Прогон
  `tests/test_push_hook_stand.py`: 3 failed —
  `test_push_replaces_policy_symlink_not_its_target`,
  `test_write_push_policy_replaces_symlink_not_its_target`,
  `test_push_hook_line_fails_on_policy_symlink_and_fix_replaces`. Код
  возвращён через `git checkout --`, `git status --short` чист.

## Предложения системе
- Отказ advance прошлого шага: разработчик вписал пояснение прямо в ячейку
  «статус» реестра (`fixed — …`), и guard отклонил переход. Стоит прямо
  указать в шаблоне `templates/REVIEW.md` или в скиле разработчика, что в
  ячейке «статус» стоит только слово статуса, а пояснение пишется в
  «решение».
