# Записка spec_auditor

## Выяснено
- Визит 3 (spec_sha af94d695…): разница с af308e64 (`git diff 8295ca3d5 e8e18a228` в refs/artifacts/<id>) — только требование 3 «Объём отказа», AC-7, строка «Не входит»; ровно решение Оператора №2. Вердикт pass.
- Ссылки на код верны на HEAD a99d020b9 (artel.py:2562, role_prompt.py:197/503, gitcmd.py:25/259/263/1123, runner.py:1017/1093).
- PATH роли у Codex переживает оболочку входа (inherit=all, codex.py:150-168) — обёртка дойдёт.
- Без TTY git pager не запускает; при TTY `-c pager.log=…` исполняется (канал вне списка решения №2 — наблюдение).
- Визит 2: git ставит exec-path первым в PATH детей; fsmonitor='git clean -fX' рекурсивно виснет.

## Не сработало
- Bash: `ls`, `cd` перед git, `$VAR`-раскрытия, `{…'…}` в python -c — под запретом; использовать Read и python3 -c без словарей.

## Где остановился
- SPEC-AUDIT.md записан, status ready, verdict pass; guard — ок. Шаг завершён.

## Чего не хватило
- Как получить прошлую версию SPEC: `git log refs/artifacts/<id> -- tasks/<id>/SPEC.md` в рабочем каталоге.
