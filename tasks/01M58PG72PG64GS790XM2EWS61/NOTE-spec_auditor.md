# Записка spec_auditor (аудит SPEC sha 2ce084c9…)

## Выяснено
- Отклонения 1-4 прежней версии закрыты: `_task_own_profile` в зоне и
  зовёт помощник (ANSWER-2 п.1), ключ базы без `tools`, AC-3 ловит префикс
  (`3.1`/`3.12.0`, `2`/`22.1`), имена строк и шов названы.
- Факты SPEC о строках кода подтвердились (cli.py:13-20/94/101,
  project_profile.py:65-99/143-167/184-192/208-220, acceptance.py:2150,
  2269, 2318-2322, 2384-2410, 2041-2048, suite_run.py:294/521-524,
  fsm_merge_gate.py:832-837/982, targets.py:84-118).
- Неточность: pull.py:665, plank_run.py:220, amend.py:548/723 не зовут
  `Profile.from_values` — зовут `acceptance._task_own_profile`, который
  задача меняет (их Profile получит `tools`; ключа они не считают).
- `_task_own_profile` возвращает `_own(profile)` (acceptance.py:121-124,
  2410): у `pult-pytest` — None, AC-12 «оба дают Profile» для артели
  невыполним буквально.
- Пробелы проверяемости: наличие инструмента по `env.PATH` (which), таймаут
  `--version`, исключение `depends_on` `via: contract` — ни один AC не ловит.
- «Не входит» опирается на ответ 3 ANSWER-1, отменённый ANSWER-2 п.1.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан.

## Чего не хватило
- Клон sled (`.artel/projects/sled…`) вне разрешённых каталогов — строки
  ci.yml:59-64 sled не сверены.
