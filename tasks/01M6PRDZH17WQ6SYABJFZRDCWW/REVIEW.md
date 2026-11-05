---
task: 01M6PRDZH17WQ6SYABJFZRDCWW
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Тест compose с настоящим Docker — каталог дополнений в подставном DOCKER_CONFIG

## Фаза A: план
- Таблица покрытия полна (требования 1–5 → шаг 1); один шаг размера MR
  адекватен объёму (помощник + одна строка теста + докстринги).
- Подход совпадает с правилом пульта: `orchestrator/acceptance.py:870-872`
  (`HOME or Path.home()`, `DOCKER_CONFIG or <home>/.docker`) — помощник
  повторяет ту же истинностную логику (пустая строка = отсутствие).
- «Влияние на систему» = diff: тронут только
  `tests/test_01m6paj61d4pyap79adrpa6mwv_compose_docker.py` (+ карта).
  Откат — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `docker_config_sandbox()` — `mkdtemp(prefix="artel-docker-config-")`, конфигурация вычисляется в момент вызова, ссылка `cli-plugins` → `Path(real)/"cli-plugins"` только при `is_dir()`. |
| 2 | OK | Кроме `os.symlink` в каталог ничего не пишется. |
| 3 | OK | `docker_config = docker_config_sandbox()` вместо `mkdtemp`; `addCleanup`/`setenv` прежние строки от того же имени, стоят после присваивания. |
| 4 | OK | Diff теста — одна строка подготовки и два дополнения докстрингов; `skipif`, утверждения `:348-349` и `finally` не тронуты (сверено по diff). |
| 5 | OK | Долгоживущий файл `tests/test_01m6prdzh17wq6syabjfzrdcww_docker_config_sandbox.py` (группа «долгоживущий») — 7 тестов, docker не зовут, конфигурации вымышленные в `tmp_path`. |

## Замечания
Нет блокирующих и значимых.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `CI=1 python3 -m pytest -p no:cacheprovider -q tests/test_01m6prdzh17wq6syabjfzrdcww_docker_config_sandbox.py tests/test_01m6paj61d4pyap79adrpa6mwv_compose_docker.py` — 12 passed, 1 skipped (прежний файл 5 passed + 1 skipped, как в SPEC; новый — 7 passed).
- `artel.py plank-run 01M6PRDZH17WQ6SYABJFZRDCWW` — отказ «планки нет: в refs/artifacts/… нет файлов test_*.py»; критерии AC-1…AC-5 закрыты долгоживущим файлом `tests/`, что согласуется с PLAN.
- Временные мутации `docker_config_sandbox`/теста (скрипт с восстановлением в `finally`, `git status` после — чисто), прогон долгоживущего файла:
  - `os.symlink` → `shutil.copytree` — 4 failed (AC-1…AC-4);
  - `DOCKER_CONFIG` «задана, если есть в окружении» вместо истинности — 1 failed (AC-2, `""`);
  - `setenv("HOME", …)` до помощника и не от его результата — 1 failed (AC-5).
- Сверка правила с `orchestrator/acceptance.py:870-872` чтением — совпадает.

## Предложения системе
- `artel.py plank-run` отказывает кодом ошибки, когда планка задачи пуста по
  замыслу (все критерии — в долгоживущем файле `tests/`); ревьюверу стоило бы
  видеть это как штатный исход «планка пуста, долгоживущие файлы: …», а не отказ.
