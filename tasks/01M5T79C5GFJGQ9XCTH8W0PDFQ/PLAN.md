---
task: 01M5T79C5GFJGQ9XCTH8W0PDFQ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Скорость пульта, git 3: чтения git из клона проекта и рабочей копии — через orchestrator/gitcmd.py

## Подход
Перенос без смены поведения. В `orchestrator/gitcmd.py` три новые функции
запуска и три именованных отказа:

- `read(repo, *args, timeout=None, input=None, text=False)` — `subprocess.run(["git", "-C", repo, …], capture_output=True, env=pult_env())`.
  Ключевые аргументы, которые вызывающий не задал, в `subprocess.run` не
  передаются: вызов тот же, что был у места (места 2, 3, 5, 6, 7). Путь — глобальный
  `subprocess.run`, поэтому `SpyRun`, шпионы `subprocess.run` тестов и подмена
  `outcome_integrity.subprocess.run` (это тот же атрибут модуля `subprocess`) видят запуск, как раньше.
  `TimeoutExpired` превращается в `gitcmd.Timeout`, `OSError` выходит наружу: каждое место разбирает
  его по-своему (127 / `_Prepare` / «git не ответил (…)» / `SOURCE_FAILED`).
- `read_env(repo, env, *args, timeout)` — место 1: `subprocess.Popen` с `-C <root>`, `cwd=config.ROOT`,
  `pult_env(env)`, текстовый вывод. По сроку вызывает `kill`, дочитывает вывод и бросает `Timeout`.
  `OSError` запуска выходит наружу (как раньше: `Popen` вне `try`). Функция идёт мимо `subprocess.run`, поэтому `SpyRun` её не перехватывает.
- `read_stream(repo, *args, limit, timeout, chunk)` — место 4: прежний цикл
  `_list_tree` (чтение порциями, таймер с `kill`, предел байт) перенесён в
  `gitcmd`. Три исхода различимы: `OverLimit`, `Timeout` и результат с кодом
  возврата. Отказ запуска (`OSError` или `TimeoutExpired` конструктора) даёт
  `LaunchFailed(error)` с исходным исключением, и место по-прежнему пишет
  `SOURCE_FAILED "ls-tree: <имя>: <текст>"`, а не `DEADLINE`.

Места меняют только запуск, разбор исходов остаётся прежним. Порядок
проверок места 4 тоже сохранён: предел → срок (таймер / `end` в `gitcmd`, затем
`deadline` места) → код. Места 2 и 3 пишут на `Timeout` прежний текст
`"git не ответил (TimeoutExpired)"`.

Выбран вариант с исключениями, а не со значением-отказом: так в местах 1–5
меньше всего правок разбора, а `TimeoutExpired` из `gitcmd` не выходит.

## Шаги
1. `gitcmd`: `Timeout`, `OverLimit`, `LaunchFailed`, `read`, `read_env`, `read_stream` (+ импорт `threading`, `time`).
2. Перевод мест: `acceptance.suite_tree_hash` (вложенная `git()` → `read_env`), `brief._clone_git` и
   `reference_cache.branch_commit` / `_cat_blobs` (→ `read`), `reference_cache._list_tree` (→ `read_stream`),
   `tz_check._git` (→ `read`), `outcome_integrity._added_lines` (→ `read`; импорт `subprocess` в модуле оставлен).
   В `reference_cache` убраны ставшие лишними импорты `subprocess` и `threading`: тесты их не патчат, grep `reference_cache\.(subprocess|threading)` по `tests/` пуст.
3. Юнит-тесты `tests/test_gitcmd_reads.py` на исходы самих функций `gitcmd` (то, чего нет в долгоживущем сторож-файле):
   три исхода потока, убийство процесса по сроку, `LaunchFailed` против `Timeout`, `Timeout` вместо `TimeoutExpired` у `read`,
   `kill` и дочитывание вывода у `read_env`. Каждый тест проверен временной мутацией (перебор предела без `OverLimit`,
   таймер без `kill`, `TimeoutExpired` запуска → `Timeout`, `read` пропускает `TimeoutExpired`, `read_env` без `kill`): все красные, код возвращён.
4. Карта `docs/codebase-map.md` регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (все семь мест через `gitcmd`, прямого git через `subprocess` нет, импорт `subprocess` в `outcome_integrity` сохранён) | 2 |
| 2 (срок, поток с пределом, байты, своё окружение на `Popen`) | 1 |
| 3 (поведение мест прежнее) | 1, 2 |
| 4 (подмены тестов) | 1, 2 — см. «Влияние на систему» |
| 5 (долгоживущий сторож) | файл `tests/test_01m5t79c5gfjgq9xcth8w0pdfq_git_guard.py` от test_author, зелёный |

Проверки: `plank-run` — 94 passed. Долгоживущий сторож и тесты AC-3
(`test_01m4s24963r9h18an2xdp6r15b_cache.py`, `test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`,
`test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, `test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py`,
`test_outcome_gate_module.py`, `test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py`) — 174 passed.
`test_invariants.py` и `test_codebase_map.py` — 118 passed. `test_acceptance.py` — 21 passed. `test_tz_check.py` и прочие файлы,
зовущие места, — в прогоне ниже.

## Влияние на систему
- **Подмена `gitcmd.git` / `in_repo` / `show` / `ls_tree_files`** (`fake_git`, `LightTransitionSandbox`): новые
  функции не зовут ни одну из них. Они запускают `subprocess` сами, как раньше места, поэтому заглушки
  исход мест не меняют (планка AC-9 зелёная).
- **`SpyRun` / шпионы `subprocess.run`**: места 2, 3, 5, 6, 7 идут через `subprocess.run` с тем же набором
  ключевых аргументов. Места 1 и 4 идут через `subprocess.Popen`, как раньше.
- **Подмена `acceptance.subprocess` целиком** (требование 4): после переноса она не перехватывает `Popen`
  места 1. Прогнал все названные в SPEC файлы — исход не изменился, все зелёные:
  `tests/test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`,
  `tests/test_01m56kcvctw5bv9twth54tw9q9_pult_pytest_unchanged.py`, `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`,
  `tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py`, `tests/test_report_outcome_module.py`,
  `tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py`. Вместе с ними прошли `test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py`,
  `test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py`, `test_01m4pmq5fqmev11wpy64g0gnxs_subtest_failures.py`,
  `test_full_suite_reuse.py`, `test_pull_additive_conflict.py`, `test_task_component_places.py` и `test_tz_check.py`:
  174 passed, 338 subtests. До `suite_tree_hash` под этой подменой доходят `PytestSpy`, а они и раньше
  отдавали git настоящему `Popen`.
- Гейты, лимиты и инварианты не трогаются. Существующие тесты не правлены. Откат — revert одного merge-коммита.

## Риски
- `gitcmd` теперь импортирует `threading`/`time`. Тесты, подменяющие `time.monotonic` глобально, действуют на
  поток так же, как раньше на `_list_tree`: там стоял тот же вызов.

## Предложения системе
- Записка test_author: Bash шага не даёт `cat`/`ls` и подстановки `$VAR`/`{…'…'}`, поэтому сценарий временной мутации
  пришлось писать файлом в рабочий каталог и удалять самим сценарием. Пригодилась бы команда пульта
  «прогон мутации из файла-патча по моим тестам» (`mutation-run` есть, но работает от ref'ов).
