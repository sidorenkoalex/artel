---
task: 01M3XVW94Z8E8R71XN7QWYMSP4
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Прогон планки после подтяжки main исполняет долгоживущую группу

# ТЗ: Прогон планки после подтяжки main исполняет долгоживущую группу; планка без .md без заголовочного блока

Источник: строка копилки 02.10 (П1) «Ложная эскалация 01M3SA3ANYZ7036AAGXZG753E3
после подтяжки main»; повтор через три минуты на 01M3XTFJCC5TG63FHW907GQM4D;
решение Оператора 02.10 — срочная малая задача.

Факты (origin/main 4abfce0c):
- После шага разработчика пульт подтягивает main в ветку задачи и
  прогоняет планку: `orchestrator/pull.py:558` —
  `acceptance.run(tdir, cwd=wt_path)` без аргумента `extra`, то есть
  только каталог `tasks/<id>/acceptance_tests/`.
- Переход `in_dev → verifying` прогоняет обе группы: разовую и
  долгоживущую (`orchestrator/advance_gates/acceptance.py:237-260` —
  перечень `long_lived_manifest`, затем
  `acceptance.run(acc_tdir, cwd=run_cwd, extra=long_lived)`). Автогейт
  приёмки делает то же после задачи 01M3RWA2786HCAC8PT3XSBKQT4.
- Планка, целиком долгоживущая по ADR-0020 (в каталоге только перечень
  `long_lived.sha256.txt` и, возможно, README), даёт после подтяжки
  pytest «collected 0 items» (код выхода 5), пульт считает это красным
  и переводит задачу в `escalated` («приёмочные тесты красные после
  подтяжки main»). 02.10 так встали 01M3SA3ANYZ7036AAGXZG753E3 (08:25Z) и
  01M3XTFJCC5TG63FHW907GQM4D (08:27Z); Оператор снимал эскалации вручную.
- В обеих планках test_author положил `acceptance_tests/README.md` без
  заголовочного блока (frontmatter). Снимок артефактной ветки при мерже
  кладёт его в main, а `scripts/guard.py --all` на main требует блок у
  любого `.md` в `tasks/` — так 30.09 main был красным 3 ч 47 мин после
  01M3RWA2786HCAC8PT3XSBKQT4. 02.10 README удалены командой `amend-tests`.
  Правила об этом в `skills/test-authoring.md` нет.

Требуется:
1. `orchestrator/pull.py`: прогон планки после подтяжки исполняет и
   разовую, и долгоживущую группу — тем же перечнем
   (`long_lived_manifest`) и тем же вызовом `acceptance.run(…, extra=…)`,
   что переход `in_dev → verifying`; без второй копии правила выбора
   файлов. Задача с непустым перечнем и пустой разовой группой не даёт
   «collected 0 items».
2. Сбой чтения перечня при подтяжке — именованный отказ (fail-closed,
   ADR-0002), не молчаливый прогон одной разовой группы.
3. Задача без перечня (прежние задачи) проходит подтяжку как сегодня.
4. `skills/test-authoring.md`: в `acceptance_tests/` не класть файлы
   `.md`; пояснения к планке — в докстрингах тестов и в PLAN/SPEC
   (снимок артефактной ветки переносит каталог в main, где `guard --all`
   требует заголовочный блок у каждого `.md`). Правка — приложением PLAN
   (защищённый путь).
5. Тесты в `tests/`, каждый с «Ловит мутацию: …»:
   а) целиком долгоживущая планка (в каталоге только перечень), main
      подтянут, долгоживущий тест зелёный — задача остаётся в `in_dev`,
      эскалации нет («Ловит мутацию: прогон после подтяжки снова берёт
      только каталог acceptance_tests/»);
   б) тот же случай с красным долгоживущим тестом — эскалация, как
      сегодня при красной планке («Ловит мутацию: долгоживущая группа
      передана, но её исход не учитывается»);
   в) перечень не читается — именованный отказ, а не зелёный прогон
      («Ловит мутацию: сбой перечня молча сводится к пустой группе»);
   г) задача без перечня — прежнее поведение.

Зоны: orchestrator/pull.py, tests/test_pull_long_lived_plank.py, docs/codebase-map.md.
Приложением: skills/test-authoring.md (защищённый путь, применяет пульт на мерже).

Только чтение (не менять): orchestrator/acceptance.py,
orchestrator/advance_gates/ (в том числе acceptance.py), orchestrator/fsm_autogate.py,
orchestrator/fsm_advance.py, orchestrator/amend.py, orchestrator/config.py,
scripts/guard.py, остальные файлы tests/, остальные файлы skills/,
docs/adr/, docs/invariants.md, tests/test_invariants.py, tasks/.

Не входит: проверка `guard --all` по снимку на гейте мержа (задача
01M3SF7DPFGEZ7VYEGGXGTX49E); отказ guard на `.md` без блока в
`acceptance_tests/` на выходе из `tests_writing`; правка уже
смерженных планок.

Рамка: $20.
