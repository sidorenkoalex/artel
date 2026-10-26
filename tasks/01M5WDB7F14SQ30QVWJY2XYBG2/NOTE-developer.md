# Записка developer — 01M5WDB7F14SQ30QVWJY2XYBG2

## Выяснено
- Ревью итерации 3 (R3-F1): назначение в теле псевдонима из argv (`-c alias.p=push <клон> main`,
  `!git -C <клон> push …`, через `--config-env`) обходило `_alias_guarded_project`.
- Исправлено (шаг 9 PLAN): `gitcmd._alias_body_words` — слова тел `alias.*` (`!` снят, `$VAR` из env,
  `shlex`, значение `--опция=`) + имена проектов из `.artel/projects/<имя>/` в тексте тела; передаются
  в `_alias_guarded_project`. Артель/`operator` прежние.
- Тест `test_alias_body_into_whitelisted_clone_from_pult_root_refused` (12 случаев) — мутация «пусто» 12 failed.
- Прогоны: 175 passed (push_point, git_hooks, multitarget, файлы задачи, А0, store), 106 passed соседние git, планка 75.
- REVIEW.md: R3-F1 размечена `fixed`.

## Не сработало
- `$(...)` в Bash роли запрещён — файлы тестов перечислял явно (`git ls-files tests | grep`).

## Где остановился
- Шаг завершён: PLAN.md status: ready, карта регенерирована.
- Остаточный риск записан в PLAN «Риски»: вычисляемый путь в `!`-псевдониме (`$(…)`) разбором не ловится.

## Чего не хватило
- Ничего существенного.
