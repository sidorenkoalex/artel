# Записка test_author

## Выяснено
- Все AC-1..AC-15 покрыты долгоживущими файлами (каталог acceptance_tests/ пуст — планки разового вида нет; plank-run без test_*.py не запускается, долгоживущие гонялись pytest напрямую):
  - tests/test_01m5wdb7jy0vjghvkcaba2qc5t_role_author.py — AC-9 (runner.role_env).
  - tests/test_01m5wdb7jy0vjghvkcaba2qc5t_rewrite_flow.py — AC-1..8, AC-10..15 (real_git, внешний проект, запись в локальном слое `targets.local_path()`).
- Зависимости (часть 1 01M5WDB7F14SQ30QVWJY2XYBG2, А1.1 01M5WCXBM7WCMRWCBWNCHMAR3T) в main нет; на main 60 из 63 красны (запись с новыми полями не грузится), зелены только сценарии записи без новых полей.
- Контракт транспорта GitLab — ANSWER-1 задачи А1.1 (В-1: A): `gitlab_adapter.transport(method,url,headers,body,timeout)->(код,заголовки,bytes)`, сеть — URLError. Исходы AC-12 — через него, `keychain.token`→None (отказ токена), и подмену `forge.token_user` с текстом «не реализовано для gitlab» (из ответа github).
- SPEC «коммит закрытия (snapshot.py:272)»: строка 272 — `_history_commit` (исторический снимок), закрытие — `snapshot.commit_closing`; тест — на commit_closing (оговорено в докстринге AC-10).
- Авторазрешение карты у внешнего проекта зовёт `scripts/codebase_map.py` самого проекта — фикстура кладёт свой генератор (заголовок с числом файлов → конфликт гарантирован).

## Валидация стабами (откачены, git status: только два новых файла tests/)
- Стаб загрузки полей в targets.py: все сценарии доходят до переходов, краснота — по делу; места merge AC-15 зелёные.
- Стабы role_env (AC-9), подписи+журнала чекпоинта (AC-10/11 чекпоинт), пакета ревью (AC-14) — зелёные; мутация «дифф от локальной main» в AC-14 поймана.

## Не сработало
- Bash: `cd …&&`, переменные shell, `rm`, `awk`, `sed` с `$` — отказ; только абсолютные пути и python3 -c.
- runner.cmd_run читает скилы из main клона артели — в песочнице нужно закоммитить skills/ и templates/.

## Где остановился
- Готово: preflight пройдена (6/6).

## Чего не хватило
- Формы результата `forge.token_user` (не задана ни SPEC, ни А1.1) — обошёл подменой транспорта.
