---
task: 01M48FRD9RJDBBVT2SN0FY5G2A
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: детерминированный тест AC-6 части 2 и ловля тестов, зависимых от случайного зерна

## Подход

Две независимые части.

**Требование 2 (рубеж `in_dev -> verifying`) — реализовано в этом шаге.**
- `orchestrator/config.py`: константа `LONG_LIVED_SEED_REPEATS = 3` (имя
  задано долгоживущим файлом задачи
  `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py`).
- `orchestrator/acceptance.py`:
  - `carries_random_seed(path)` — признак «несёт случайное зерно»: разбор
    `ast`, узлы `import random` (в т.ч. `as`, через запятую) и
    `from random import …` в любом месте файла; слово `random` в
    строке/комментарии и `from .random import` признаком не являются.
  - `run_repeat(files, cwd, command)` — один повтор долгоживущих файлов
    без планки, с пределом `config.ACCEPTANCE_TIMEOUT_SEC`. Красные тесты
    и их зёрна — из отчёта junit pytest (`--junitxml`,
    `-o junit_logging=system-out`): хвост текстового вывода обрезан до
    2000 символов и не связывает зерно с конкретным тестом. Узел
    `файл::Класс::метод` строится из `classname`/`name` отчёта по
    перечню файлов. Истёкший предел и красный исход без названных
    отчётом тестов — красный повтор по каждому файлу с пометкой причины
    (не пропуск).
- `orchestrator/advance_gates/acceptance.py::_seed_repeats_escalate` —
  вызывается в `_acceptance_run_body` только после ЗЕЛЁНОГО первого
  прогона планки и долгоживущих файлов (красный первый прогон — прежний
  отказ, повторов нет). Файлы с импортом `random` гоняются
  `config.LONG_LIVED_SEED_REPEATS` раз (значение читается в момент
  рубежа), повторы не обрываются на первом красном. Любой красный повтор —
  `store.set_state(..., "escalated")` с `escalated_from="in_dev"`;
  деталь (журнал `state -> escalated` и вывод `advance`) — «тест зависит
  от случайного зерна: …», по каждому узлу — номера красных повторов и
  «зерно: N» либо «зерно не напечатано».

**Требование 1 (метод AC-6 части 2) — эскалация за мандатом** (SPEC,
требование 1: «разработчик эскалирует точный список, мандат на смену
выдаёт Оператор; без мандата метод не меняется»). В этом шаге метод НЕ
изменён; ниже — точный список и проверенный диф предлагаемой правки.

Ключевое наблюдение для выбора формы правки. Буквальный вариант «по
черновику MR на каждую запись» (36 вызовов `draft_for`) проверен
временной правкой (файл возвращён): сам метод — 193 с, а планка гоняет
метод трижды (AC-1/AC-2 один раз, AC-3 под двумя мутациями) — прогон
`plank-run` оборван пределом 300 с (`config.ACCEPTANCE_TIMEOUT_SEC`), т.е.
рубеж `in_dev -> verifying` был бы красным всегда. Поэтому предлагается
форма «один черновик на сценарий, подтест на каждую запись»: дифф
сценария содержит путь под КАЖДОЙ записью `config.PROTECTED_PATHS`,
перечень путей комментария разбирается один раз, отсутствие каждого
пути пульта проверяется своим `subTest`. Проверено временной правкой
(файл возвращён): метод — 1 passed, 36 subtests passed за 30,7 с;
`plank-run` — 4 passed за 37,5 с (AC-1, AC-2, AC-3 обе мутации).
`git apply --check` дифа ниже на чистом дереве ветки — проходит.

## Шаги

1. Требование 2: константа, `carries_random_seed`/`run_repeat`,
   `_seed_repeats_escalate`; юнит-тесты `tests/test_acceptance_seed_repeat.py`
   на углы, не покрытые долгоживущим файлом задачи; регенерация
   `docs/codebase-map.md`. — сделано.
2. Требование 1: правка метода AC-6 по мандату Оператора (диф ниже). —
   ждёт ответа на эскалацию.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 (после мандата) |
| 2 | 1 |
| 3 | 1 (долгоживущий файл test_author + `tests/test_acceptance_seed_repeat.py`) |

## Проверки этого шага

- `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py` (AC-4..AC-7) —
  6 passed за 82,6 с.
- `tests/test_acceptance_seed_repeat.py` — 4 passed, 9 subtests.
  Временные мутации (код возвращён): признак по подстроке
  `"import random"`, зёрна из вывода всех тестов прогона, повтор без
  `timeout=` — красные все тесты файла, кроме «тест без строки зерна»,
  чью заявку эти мутации не задевают.
- Тесты затронутых модулей: `test_acceptance.py`,
  `test_acceptance_collect.py`, `test_acceptance_pycache.py`,
  `test_long_lived_transitions.py`, `test_fsm_advance_gate_smoke.py`,
  `test_codebase_map.py` — 77 passed, 26 subtests.
- `plank-run` на текущем коде: AC-3 зелёный, AC-1/AC-2 красные (метод не
  изменён — ждёт мандата); на временной правке по дифу ниже — 4 passed.
- Полный набор: `suite-run` №1 оборван пределом 900 с (машина загружена,
  прогон базы тоже не завершился): прошло 2599, упало 1, пропущено 2.
  Упавший — `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  (`0 not greater than or equal to 1`); красный и повтором `--failed`
  (№2), и одиночным прогоном. `orchestrator/liveness.py` и
  `tests/test_liveness.py` от `main` не отличаются, правка задачи их не
  касается — вероятно окружение шага роли (в этом же шаге не нашлась даже
  `ls` по PATH). Базой не разделён (база не досчитана).

## Влияние на систему

- Рубеж `in_dev -> verifying` удлиняется на N прогонов долгоживущих
  файлов задачи с импортом `random` (оценка SPEC: ~15 с — ~2,6 мин при
  N = 3); у задач без таких файлов — без изменений.
- Новый исход рубежа: `in_dev -> escalated` (раньше — только отказ или
  `verifying`). Красный первый прогон — прежний отказ, байт-в-байт.
  Существующие тесты и гейты не ослабляются; гейт неослабления не
  затронут (тесты `tests/` в этом шаге не меняются, только добавлен новый
  файл).
- Откат — revert коммитов задачи; константа и функции новые, чужие
  вызовы не меняют.

## Риски

- Junit-отчёт с выводом теста зависит от встроенного плагина pytest
  `junitxml`; профиль тестов проекта с командой не-pytest повторы
  исполнит, но красный исход без отчёта назовёт по файлам с пометкой.
- Зерно в отчёте берётся из вывода красного теста (`system-out`) и текста
  провала; тест, печатающий несколько строк «зерно: …», получит все.

## Эскалация

- **Вопросы** (по блокирующести):
  1. Мандат на смену утверждений долгоживущего метода (требование 1 SPEC).
     Список: `tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py::DraftMrHighlightTest::test_ac6_highlight_lists_no_paths_and_omits_artel_only_paths`.
     Было: путь пульта — `self.rng.choice(config.PROTECTED_PATHS)` (по
     одному случайному в двух сценариях); `assertTrue([c for c in
     comments if rel in c])` по каждому пути `no_paths`;
     `assertNotIn(artel_path, text)` подстрокой всего текста комментариев
     (дважды).
     Стало: в обоих сценариях дифф несёт путь под каждой записью
     `config.PROTECTED_PATHS`; перечень путей, названных комментарием,
     разбирается регуляркой `HIGHLIGHT_PATHS` (метод-помощник
     `highlighted`, утверждение `assertIsNotNone(match)` на каждый
     комментарий); `assertIn(rel, named)` по каждому пути `no_paths`;
     `assertNotIn(artel_path, named)` — `subTest` на каждую запись в
     каждом сценарии (36 подтестов при 18 записях). Строка «Ловит
     мутацию» — без изменений. Точный диф — раздел «Предлагаемая правка
     метода AC-6».
     Варианты: (а) мандат на диф как есть — строкой ANSWER
     `Ослабление тестов разрешено: tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py::DraftMrHighlightTest::test_ac6_highlight_lists_no_paths_and_omits_artel_only_paths`;
     (б) буквальный вариант «отдельный черновик на каждую запись» — метод
     193 с, планка задачи превышает предел прогона 300 с (нужно решение
     по пределу или планке);
     (в) иная форма — опиши.
     Дефолт при молчании: (а).
- **Контекст**: требование 2 реализовано и проверено (см. «Проверки
  этого шага»); метод AC-6 не тронут; планка AC-1/AC-2 красна до правки
  метода.
- **Блокирует**: правку метода AC-6 (требование 1, AC-1..AC-3) и сдачу
  PLAN `ready`.

## Предлагаемая правка метода AC-6

Проверена `git apply --check` на чистом дереве ветки задачи.

```diff
diff --git a/tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py b/tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py
index b4f76d39..dfd89878 100644
--- a/tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py
+++ b/tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py
@@ -19,6 +19,7 @@
 Зерно печатается и входит в текст каждого провала.
 """
 import random
+import re
 import subprocess
 import unittest
 from unittest import mock
@@ -29,6 +30,9 @@ from tests.sandbox import RealGitSandbox, make_project_repo
 ARTEL = config.DEFAULT_TARGET
 EXT = "vnesh"
 ALPHABET = "abcdefghijklmnopqrstuvwxyz"
+# Перечень путей в тексте подсветки `github_adapter.ensure_draft_mr`:
+# «… затрагивает защищённые пути: a, b (<источник перечня>).»
+HIGHLIGHT_PATHS = re.compile(r"затрагивает защищённые пути: (.+) \(")
 
 TARGET_ENTRY = """  {name}:
     forge: github
@@ -129,16 +133,29 @@ class DraftMrSandbox(RealGitSandbox):
 
 class DraftMrHighlightTest(DraftMrSandbox):
 
+    def highlighted(self, comments: list[str]) -> list[str]:
+        """Пути, которые назвали комментарии подсветки: перечень между
+        «защищённые пути: » и « (<источник перечня>)» — не весь текст, в
+        котором источник «no_paths проекта … в targets.yaml» назван всегда."""
+        named: list[str] = []
+        for comment in comments:
+            match = HIGHLIGHT_PATHS.search(comment)
+            self.assertIsNotNone(match, self.explain(
+                f"комментарий без перечня путей: {comment}"))
+            named.extend(match.group(1).split(", "))
+        return named
+
     def test_ac6_highlight_lists_no_paths_and_omits_artel_only_paths(self):
         """Комментарий черновика MR внешнего проекта называет пути диффа под его `no_paths` и не называет пути, защищённые только у артели.
 
         Сценарий: дифф задачи внешнего проекта — файл кода, один-два пути под
-        записями `no_paths` проекта и путь под случайной записью
-        `config.PROTECTED_PATHS` (её нет в `no_paths`). После
-        `ensure_draft_mr` есть комментарий `gh pr comment`, называющий каждый
-        путь `no_paths`, и ни один комментарий не называет путь пульта.
-        Вторая задача — файл кода и только путь пульта: ни один комментарий
-        его не называет.
+        записями `no_paths` проекта и по пути под КАЖДОЙ записью
+        `config.PROTECTED_PATHS` (их нет в `no_paths`). После
+        `ensure_draft_mr` перечень путей, названных комментариями
+        `gh pr comment`, содержит каждый путь `no_paths` и — подтестом на
+        каждую запись перечня пульта — не содержит её путь. Вторая задача —
+        файл кода и только пути под каждой записью перечня пульта: перечень
+        не содержит ни одного (подтест на запись).
 
         Ловит мутацию: подсветка сверяет дифф с `config.PROTECTED_PATHS` для
         любого проекта — пути `no_paths` выпадают из комментария (или
@@ -147,21 +164,26 @@ class DraftMrHighlightTest(DraftMrSandbox):
         """
         ext_paths = [self.under(e) for e in
                      self.rng.sample(self.no_paths, self.rng.randint(1, 2))]
-        artel_path = self.artel_only_path()
+        artel_paths = {e: self.under(e) for e in config.PROTECTED_PATHS}
         code = f"kod{self.word()}/{self.word()}.py"
-        comments = self.draft_for([code, artel_path] + ext_paths)
-        text = "\n".join(comments)
+        comments = self.draft_for([code, *artel_paths.values(), *ext_paths])
+        named = self.highlighted(comments)
         for rel in ext_paths:
-            self.assertTrue([c for c in comments if rel in c], self.explain(
+            self.assertIn(rel, named, self.explain(
                 f"путь no_paths {rel} не подсвечен: {comments}"))
-        self.assertNotIn(artel_path, text, self.explain(
-            f"путь пульта {artel_path} подсвечен: {comments}"))
+        for entry, artel_path in artel_paths.items():
+            with self.subTest(scenario="no_paths и пути пульта", entry=entry):
+                self.assertNotIn(artel_path, named, self.explain(
+                    f"путь пульта {artel_path} подсвечен: {comments}"))
 
-        artel_path = self.artel_only_path()
+        artel_paths = {e: self.under(e) for e in config.PROTECTED_PATHS}
         comments = self.draft_for([f"kod{self.word()}/{self.word()}.py",
-                                   artel_path])
-        self.assertNotIn(artel_path, "\n".join(comments), self.explain(
-            f"путь пульта {artel_path} подсвечен: {comments}"))
+                                   *artel_paths.values()])
+        named = self.highlighted(comments)
+        for entry, artel_path in artel_paths.items():
+            with self.subTest(scenario="только пути пульта", entry=entry):
+                self.assertNotIn(artel_path, named, self.explain(
+                    f"путь пульта {artel_path} подсвечен: {comments}"))
 
 
 if __name__ == "__main__":
```

## Предложения системе

- skills/test-authoring.md: планка, исполняющая дорогой долгоживущий
  метод несколько раз (здесь AC-3 — под каждой мутацией), сама упирается
  в `config.ACCEPTANCE_TIMEOUT_SEC` = 300 с на общий прогон планки и
  долгоживущих файлов рубежа; автор тестов этот бюджет времени не видит.
- `suite-run`: полный набор не уложился в 900 с при загруженной машине,
  база не досчиталась — упавшие не делятся по базе; в окружении шага роли
  `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  красный при неизменном коде (проверить, не в окружении ли шага дело).
