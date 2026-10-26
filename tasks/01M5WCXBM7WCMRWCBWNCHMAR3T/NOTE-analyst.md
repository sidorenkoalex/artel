# Записка analyst — 01M5WCXBM7WCMRWCBWNCHMAR3T

## Выяснено
- Возврат с spec_gate (6 решений) закрыт правкой SPEC:
  - Д-2 (б): `policy.ci_required_jobs` читается как необязательное (нет
    поля — пусто); targets.py не трогаем; в «Не входит» — объявление поля
    у Б1 = 01M5WDB7F14SQ30QVWJY2XYBG2 и условие не открывать
    SUPPORTED_FORGES для gitlab до его мержа.
  - Д-1: новый AC-21 (ast: ci.py читает поле forge только как аргумент
    вызова forge; forge.py — индекс реестра, без сравнений).
  - Д-3: старшинство red → unknown → running → none → green в требовании
    5; failed без права падать — red при любом статусе конвейера, кроме
    неполной выдачи (unknown); created не за manual → running, skipped
    не за manual → unknown (AC-5 переписан); новый AC-22 на сочетания.
  - Ф-2: (None, None) из gitcmd.hosting_token (gitcmd.py:121) для gitlab
    — «токен не получен», запроса нет; target — имя проекта (str); AC-3.
  - AC-17: ловит ImportFrom из urllib/http.client и вызов по псевдониму
    вне транспорта; urllib.error-исключения разрешены.
  - Строка срока токена (часть 2): skip при ошибке HTTP/сети, для github
    строки нет — в «Не входит».
- В ci.py сейчас нет ни одного упоминания `forge`.
- created/skipped из ci_required_jobs оставлены «не green» — решение гейта
  называло только случай «не за ручным».

## Не сработало
- `ls` в Bash недоступен; составные команды с `cd` — нет.

## Где остановился
- SPEC.md: 22 AC, status ready, budget 50, guard: ок. Шаг завершён.

## Чего не хватило
- Полный id Б1 по префиксу: нашёлся через
  `git for-each-ref 'refs/artifacts/01M5WDB7F1*'`.
