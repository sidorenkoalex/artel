---
task: 01M6JJ4J4NBV2Y1Q4XHE3C3FVT
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Граница git для ролей — отказ git clean и git в репозитории пульта, команда удаления файла задачи

## Фаза A — план
- Таблица покрытия полна (требования 1–10). Шаг 9 закрывает R1-F1..F3 и называет конкретные тесты и мутации. Пробел итерации 1 (в `tests/` не было сквозного сторожа) план закрыл.
- «Влияние на систему» сходится с инкрементальным diff: `orchestrator/role_git.py`, `orchestrator/task_files.py`, `tests/test_role_git.py`. Все три файла в зонах SPEC, существующие тесты не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1. AC-1 зелёный в планке |
| 2 | OK | Без изменений. Сторож — `WrapperMainTest::test_foreign_copy_and_pult_root_refused_with_own_reason` |
| 3 | OK | `role_git._alias_refusal:276-289`: тело псевдонима разбирается `parse()`, значение `-c`/`--config-env` не считается подкомандой. Конфигурация тела проверяется: pager/fsmonitor с git и `core.worktree` дают отказ, `alias.*` тела участвуют в раскрытии. Проверено через настоящую обёртку (см. ниже) |
| 4 | OK | `task_files.py:46`: повтор пути пропускается, и второго `unlink` нет |
| 5 | OK | Сторож — `DispatcherPathTest` |
| 6 | OK | Без изменений |
| 7 | OK | Сторож — `DoctorBoundaryTest` (`ok`, а также `fail` без потолка и без обёртки; временный каталог убран) |
| 8 | OK | Без изменений |
| 9 | OK | Без изменений |
| 10 | OK | Без изменений |

## Замечания
Новых замечаний нет. Проверил тесты нового diff по их заявкам «Ловит мутацию»: каждая заявленная мутация внесена временно, и на каждой тест красный (см. «Проверено исполнением»). Отдельно проверил мутацию «отказ `sub == "clean"` выключен». В одиночку она эквивалентна, потому что `_alias_refusal` отклоняет слово `clean` сам. Разработчик честно написал об этом в заявке; выключение обоих мест красит 4 теста.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/role_git.py:276-289 | Тело псевдонима с `-c k=v` перед `clean`; конфигурация `-c` в теле не проверялась | Обход отказа `git clean` (требование 3) | Принято: разбор тела через `parse()` и проверка `option_config`. Через настоящую обёртку отклоняются `-c 'alias.cl=-c a.b=c clean -fX' cl`, `--config-env` в теле, цепочки `-c alias.z=clean z`, `-c alias.z=!git clean -fX z` и вложенная цепочка псевдонима с `-c`. Файл цел; `-c color.ui=never log` проходит к git |
| R1-F2 | accepted | tests/test_role_git.py | В `tests/` не было сторожа ядра | Регрессия проходила бы CI | Принято: все 7 мутаций итерации 1 и мутации R1-F1/R1-F3 красят `tests/test_role_git.py` |
| R1-F3 | accepted | orchestrator/task_files.py:46 | Повтор пути не отсекался | Трассировка `FileNotFoundError` | Принято: `elif item not in planned`. Сторож — `TaskRmCommandTest::test_repeated_path_removed_once` (мутация → красный) |

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M6JJ4J4NBV2Y1Q4XHE3C3FVT`: 119 passed, код выхода pytest 0.
- `python3 -m pytest -p no:cacheprovider -q tests/test_role_git.py tests/test_01m6jj4j4nbv2y1q4xhe3c3fvt_role_git_boundary.py tests/test_multitarget.py`: 76 passed, 14 subtests passed.
- Временные мутации. Скрипт лежал в каталоге документов и удалён; каждая правка возвращена в `finally`, `git status --short` после прогона пуст. На каждой мутации `tests/test_role_git.py` и долгоживущий файл задачи красные:
  - foreign-отказ выключен: 1 failed;
  - `reason = None`: 1 failed;
  - оба отказа `clean` выключены: 4 failed;
  - старый разбор тела псевдонима: 2 failed;
  - `_command_refusal(body)` выключен: 1 failed;
  - отказ `core.worktree` в теле выключен: 1 failed;
  - диспетчер не снимает PATH: 1 failed;
  - проверка `task_id != ARTEL_TASK` выключена: 1 failed;
  - `task-rm` убран из `docs_dir_note`: 1 failed;
  - doctor не отдаёт `fail`: 1 failed;
  - дедупликация `planned` убрана: 1 failed.
- Настоящая обёртка `orchestrator/role_bin/git`, дублёр корня во временном каталоге, `ARTEL_TASK`/`ARTEL_GIT_GUARD_ROOT`/потолок выставлены, в своей копии лежит игнорируемый `j.log`:
  - отклоняются с кодом 1 и строкой `task-rm` (`j.log` на месте) пять форм: `-c 'alias.cl=-c a.b=c clean -fX' cl`, `--config-env=a.b=HOME clean -fX` в теле, `-c alias.z=clean z -fX` в теле, `-c alias.z=!git clean -fX z` в теле, двухуровневая цепочка с `-c` в теле вложенного псевдонима;
  - проходят к git `-c 'alias.lg=-c color.ui=never log --oneline' lg` и `status --short` (код 0).

## Предложения системе
- Два из трёх замечаний итерации 1 (R1-F2, а косвенно и R1-F1) выросли из пометки «разовый» на свойствах кода в планке. Предложение итерации 1 для `skills/test-authoring.md` остаётся в силе: test_author называет тест `tests/`, обязанный держать свойство, которое ушло в «разовый» из-за ограничения guard.
