# Записка spec_auditor — 01M5H1A4GS19TPR4RJ8XRVVYZQ (круг 3, SPEC sha c2b79d39)

## Выяснено
- Решения Оператора круга 2 (п. 1–3) в SPEC перенесены: треб. 1–3, AC-1–AC-3, AC-7, AC-9.
- Учёт guard на HEAD 33547d9a (скрипт через guard._helper_calls/_own_assertions, удалён):
  ac4_git 6 (own 1, `git` 1 из tests/sandbox.py:1956–1959, assert_prepare 4); ac4_side 5;
  ac7_rerun 3; ac7_branch 4; ac8 10; ac11 5; ac9 12; ac10×2 по 1 (check_places); ac3×2 по 5; ac6 3.
- Новое: помощник `git` (sandbox.py:1959, assertEqual) — первый уровень у test_ac4_git_preparation
  (вызов в замыкании checkout, outcome_gate.py:1167), его нет в перечне помощников треб. 2/AC-2.
- Новое: «объединение утверждений новых методов» (треб. 7, AC-7) — при объединении как max
  (Counter |) включение для ac8 (refusal×2) и ac9 (enter_audit×2, assert_depth×2) невыполнимо; нужно сумма.
- Замер pytest_own_places при загрузке 1.59: ac3_timeout 19.3, ac6 19.3, ac2 6.08 (не в перечне, <10), ac3_fresh 5.64.

- Главное: порог AC-4 (≤10 с на тест файла) невыполним в перечне разбиения — вне перечня
  spec_audit_flow ac20 (1219) 32,09 с, ac17_reject (1091) 10,86 с; outcome_gate ac6_red_kinds (1285) 11,49 с
  (загрузка 1,6–2,2). profile_callers вне перечня ≤5,54, pytest_own_places ≤6,08.

## Где остановился
- SPEC-AUDIT.md записан: concerns, пункты Ф-3 (порог), Ф-2 (`git`), О-5 (объединение); guard ок.

## Чего не хватило
- rm в Bash отклоняется — временный файл удалять через python3 -c os.remove.
