---
task: 01M4JN2EDQP8Q3WVYK0TS95ZVC
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сетевые адреса в tests/ — пульт ловит до CI

## Подход
Один источник правила — `scripts/guard.py`, новый раздел «Сетевые адреса в
`tests/`»:
- `NETWORK_ADDRESS_RE`, `NETWORK_EXEMPT_HOSTS`, `NETWORK_ADDRESS_EXCEPTIONS`
  (четыре пары с прежними обоснованиями, перенесены дословно из
  `tests/test_invariants.py::NoNetworkAddressesInTestsTest`);
- `network_address_host(url)` — хост без порта и пути (прежний `_host_of`);
- `network_address_hits(name, text) -> [(строка, адрес)]` — сама функция
  правила: точное сравнение хоста, исключение по паре (имя файла, хост);
- `network_address_errors_from_files(files)` — ошибки `«<метка>:<строка>:
  сетевой адрес «…» …»` по (метка, текст); ключ исключения — последний
  сегмент метки (ответ на вопрос «Материалов» SPEC: на выходе из
  `tests_writing` метка долгоживущего файла — его путь `tests/<имя>`, имя
  файла совпадает с ключом исключения).

Рубеж 1 (требование 2): `long_lived_errors_from_files` дописывает к
признакам файла `network_address_errors_from_files` — тот же узел, что у
прочих признаков; выход из `tests_writing` отказывает `LONG_LIVED_ACTION`
без правки `tests_writing.py` по этому пути. Признак добавлен в
`long_lived_errors_from_files`, а не в `long_lived_sign_hits`: исключения
ключуются именем файла, а `long_lived_sign_hits` получает только текст.
Признак только у артели (замечание ревью R1-F1): инвариант 35 — правило
дерева `tests/` пульта. `long_lived_errors_from_files` несёт именованный
параметр `network_addresses` (умолчание `True` — зафиксированный
долгоживущий файл зовёт функцию без него и остаётся зелёным); гейты
`_tests_writing_test_groups_gate` и `_tests_writing_long_lived_gate`
принимают тот же параметр, `fsm_advance.tests_writing` передаёт
`repo_context.is_artel(target)` — то же условие проекта, что у рубежа
`in_dev`. Канарейка target артели проверяется, как и прочими признаками
гейта групп (`test_canary_task_of_default_target_is_checked`).
Остаток: `amend-tests` (`orchestrator/amend.py:510`, файл только для
чтения) зовёт узел без параметра — правка долгоживущего файла с
DNS-адресом отказывает у любого проекта, включая чужой. Это следствие,
названное в «Материалах» SPEC; сузить его можно только правкой `amend.py`
(вне зон) — см. «Предложения системе».

Рубеж 2 (требование 3): `_network_address_gate(conn, task_id, t)` в
`orchestrator/advance_gates/tests_writing.py` (рядом с `_origin_push_gate`,
тоже гейтом `in_dev`), вызов — в `fsm_advance.in_dev` через `_run_gates`
сразу за `_review_rework_gate_refuses`, до `_origin_push_gate`: задача не
уходит в CI, старшинство прежних отказов не меняется. Гейт читает дифф
кодовой ветки против базы (`gitcmd.diff_base` + `diff_name_status(...,
"tests")`), берёт записи `tests/**/*.py` кроме удалений (у переименования —
новый путь), тексты — `gitcmd.show` с головы ветки; файлы вне диффа не
читаются (AC-4). Сбой git — отказ (ADR-0002), идиома `base is None` — как у
`_mutation_claim_gate`. Канарейка и проект не-артель — пропуск: инвариант
35 — правило дерева `tests/` пульта.

Класс отказа: нарушение чинит разработчик, нужен класс «чинит роль».
`refusal_classes.py` вне зон задачи, своё действие туда не внести —
поэтому `NETWORK_ADDRESS_ACTION = "переход отклонён"` (историческое
действие класса «чинит роль», как у `_freshness_refuses`), правило и
файл:строка — в `detail`. Сбой git — `NETWORK_ADDRESS_GIT_ACTION` вне
перечня, то есть «чинит Оператор». См. «Предложения системе».

Инвариант 35 (требование 1): приложение ниже — класс зовёт
`guard.network_address_hits`, копия правила (`_URL_RE`, `_EXEMPT_HOSTS`,
`_EXCEPTIONS`, `_host_of`) удаляется. Имена и утверждения тестовых
методов не меняются: `test_no_dns_hostname_addresses_in_tests_tree` — тот
же `assertEqual({}, offenders)`, `test_synthetic_dns_hostname_fixture_is_caught`
— тот же `assertEqual([url], hits)` через `_dns_addresses` (оставлен, теперь
обёртка над функцией guard с пустым именем файла — ни одна пара исключения
не совпадает, как и прежде у `_dns_addresses` без фильтра исключений).

## Шаги
1. `scripts/guard.py`: раздел правила адресов, вызов из
   `long_lived_errors_from_files`.
2. `orchestrator/advance_gates/tests_writing.py`: `_network_address_gate`,
   `NETWORK_ADDRESS_ACTION`, `NETWORK_ADDRESS_GIT_ACTION`;
   `orchestrator/fsm_advance.py`: импорт-реэкспорт и вызов в `in_dev`.
3. `tests/test_network_address_gate.py` — юнит-тесты свойств рубежа, не
   покрытых долгоживущим файлом и планкой: fail-closed на сбое
   `diff_base`/`diff_name_status`/`show`, отбор записей (удаление,
   переименование, не-`.py`), пропуск канарейки и чужого проекта, класс
   отказа «чинит роль» через каркас `_run_gates`.
4. Приложение к `tests/test_invariants.py` (ниже), `docs/codebase-map.md`
   регенерирована (`python3 scripts/codebase_map.py`).
5. Итерация 2 (R1-F1): параметр `network_addresses` в
   `guard.long_lived_errors_from_files` и обоих гейтах выхода из
   `tests_writing`, `fsm_advance.tests_writing` передаёт
   `repo_context.is_artel(target)`. Тесты:
   `tests/test_network_address_gate.py::LongLivedNetworkAddressScopeTest`
   (флаг guard снимает только признак адресов; гейт «только добавление»
   передаёт флаг) и
   `tests/test_fsm_advance_tests_writing_test_groups.py::TestGroupsGateTest::test_network_address_sign_only_for_artel`
   (подключение в `fsm_advance`).

Проверки шага: долгоживущий `tests/test_01m4jn2edqp8q3wvyk0ts95zvc_network_address.py`
— 5 passed (33 подтеста); планка `plank-run` — 5 passed; приложение
наложено временно — `NoNetworkAddressesInTestsTest` и долгоживущий файл
зелёные (7 passed), файл возвращён к HEAD; `git apply --check` приложения
на чистом дереве — проходит. Тесты затронутых модулей
(`test_fsm_advance_gate_smoke`, `test_long_lived_transitions`,
`test_refusal_classes`, `test_01m44enqcrk02t2mwzb9hc3xhh_origin_push`,
`test_branch_freshness_gate`, `test_advance_guard`,
`test_acceptance_tests_flow`, `test_multitarget`, `test_amend`,
`test_01m4jd3srn66sd6bm63xaghb11_in_dev_appendix`,
`test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals`,
`test_mutation_claim_gate`, `test_01m446wevjxarr5cded8re9ccr_auto_refusal_class`)
— зелёные. Полный набор `suite-run` в шаге НЕ прогнан: три попытки
получили отказ замка «на машине уже идёт прогон гейта задачи
01M4JD36367E5CG3GXDV429XTE (pid 31828)»; полный набор держат гейт приёмки
и CI ветки. Мутации: `network_address_hits` возвращает `[]` — долгоживущий
файл (AC-1/6/7) и юнит-тесты красные; переименование по старому пути без
пропуска удалений — красный `test_entry_selection`; снятые условия
канарейки/артели — красный `test_canary_and_foreign_project_skip`.

Проверки итерации 2: мутации (временно, код возвращён): `fsm_advance`
передаёт `network_addresses = True` вместе с «гейт «только добавление»
зовёт узел без флага» — красные ровно
`test_network_address_sign_only_for_artel` (подключение) и
`test_long_lived_gate_passes_flag_through` (гейт); guard игнорирует флаг
(`if True:`) — красные все три новых теста. Тесты
затронутых модулей (`test_network_address_gate`,
`test_fsm_advance_tests_writing_test_groups`, долгоживущий файл задачи,
`test_fsm_advance_gate_smoke`, `test_long_lived_transitions`,
`test_refusal_classes`, `test_amend`, `test_project_profile_gates`,
`test_docs_dir_layout`, `test_external_code_copy_refusal`,
`test_codebase_map`) — 139 passed; `plank-run` — 5 passed, код выхода 0.
Полный набор `suite-run` №1 (с приложением PLAN): одно новое падение —
`NoNetworkAddressesInTestsTest::test_no_dns_hostname_addresses_in_tests_tree`
на адресе-образце в докстринге моего нового теста (тот самый класс
задачи); докстринг переписан без адреса, `suite-run --failed` №2 —
зелёный. Прочих новых падений против базы нет.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 4 |
| 2 | 1 |
| 3 | 2, 3 |
| 4 | 1 (исключения перенесены дословно; проверено AC-5 долгоживущего файла и планки) |

## Влияние на систему
- Инвариант 35 не ослабляется: шаблон, исключённые хосты и четыре пары
  перенесены побайтно, сравнение хоста — то же точное; набор ловимых
  адресов не сужается. До наложения приложения инвариант держит свою
  копию — расхождения нет (AC-6 зелёный и на текущем инварианте).
- Выход из `tests_writing` у артели строже: долгоживущий файл с
  DNS-адресом теперь отказ (раньше — красный CI после). У чужого проекта
  выход из `tests_writing` не меняется (признак снят по
  `repo_context.is_artel(target)`); канарейка target артели проверяется.
- `amend-tests` строже у ЛЮБОГО проекта с профилем: `amend.py` (только
  для чтения) зовёт узел без параметра, поэтому правка долгоживущего
  файла с DNS-адресом отказывает и у чужого проекта — следствие, названное
  в «Материалах» SPEC; сужение — отдельной правкой `amend.py`.
- `in_dev -> verifying` получает новый рубеж за прежними; существующие
  сценарии, где git в песочнице отдаёт пустую базу, проходят (идиома
  `base is None`, как у гейта заявки мутации). Канарейка и внешние проекты
  этим рубежом не проверяются.
- `amend.py`, `refusal_classes.py`, прочие файлы «только для чтения» не
  менялись.
- Откат: revert merge-коммита задачи; приложение откатывается тем же
  revert'ом (тот же коммит мержа).

## Риски
- Действие отказа рубежа `in_dev` — общее «переход отклонён» без суффикса:
  в журнале его отличает только `detail`. Своё действие требует правки
  `refusal_classes.py` вне зон задачи.
- Гейт неослабления на `tests/test_invariants.py` из приложения: удалены
  только помощники без утверждений (`_host_of`) и атрибуты класса;
  методы и их утверждения те же.

## Приложение 1: tests/test_invariants.py — инвариант 35 зовёт функцию guard

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index fc99473c..86dfb77b 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -1889,50 +1889,23 @@ class NoNetworkAddressesInTestsTest(unittest.TestCase):
     Хост сравнивается ТОЧНО, не префиксом (`127.0.0.1.evil.example` —
     DNS-имя, лишь начинающееся с исключённого `127.0.0.1`, не сам
     loopback — обязан быть пойман, не пропущен).
-    """
-
-    _URL_RE = re.compile(r"https?://[^\s'\"]+")
-    _EXEMPT_HOSTS = ("localhost", "127.0.0.1")
 
-    # (имя файла, хост) -> обоснование: адрес — decorative/тестовый текст,
-    # никогда не передаётся реальному сетевому вызову, поэтому исключён
-    # из скана (SPEC 01M1QHQ277PQQA894X97RVEX9Y, требование 3).
-    _EXCEPTIONS = {
-        ("test_github_adapter.py", "github.com"):
-            "stdout уже замоканного `gh` (github_adapter.ci.gh подменена "
-            "лямбдой в setUp самого теста) — тест не открывает соединение "
-            "по этому адресу, строка лишь имитирует формат вывода "
-            "`gh pr create`",
-        ("test_ci_status.py", "api.github.com"):
-            "текст внутри сообщения об ошибке уже замоканного `ci.gh` "
-            "(`set_check_runs` подменяет ответ целиком) — адрес не "
-            "аргумент реального вызова, тест не обращается к сети",
-        ("test_sandbox.py", "example.invalid"):
-            "статические строки-фикстуры, проверяющие саму логику "
-            "распознавания DNS-адреса (`_is_local_git_address`/"
-            "`_network_git_command_denial`) — никогда не передаются "
-            "реальному `subprocess.run`, только сравниваются как текст",
-        ("test_sandbox.py", "127.0.0.1.evil.example"):
-            "та же статическая фикстура — хост, лишь НАЧИНАЮЩИЙСЯ с "
-            "loopback-адреса, проверяет точность сравнения хоста в "
-            "`_is_local_git_address`, тоже не передаётся `subprocess.run`",
-    }
-
-    @classmethod
-    def _host_of(cls, url: str) -> str:
-        rest = url.split("://", 1)[1]
-        return rest.split("/", 1)[0].split(":", 1)[0]
+    Правило — шаблон адреса, исключённые хосты, именованные исключения по
+    паре (имя файла, хост) с обоснованиями — живёт одной функцией
+    `guard.network_address_hits` (SPEC 01M4JN2EDQP8Q3WVYK0TS95ZVC,
+    требование 1): её же зовут выход из `tests_writing` и рубеж
+    `in_dev -> verifying`, копии правила здесь нет.
+    """
 
     def _dns_addresses(self, text: str) -> list:
-        return [m.group(0) for m in self._URL_RE.finditer(text)
-                if self._host_of(m.group(0)) not in self._EXEMPT_HOSTS]
+        # Пустое имя файла не совпадает ни с одной парой исключения.
+        return [url for _line, url in guard.network_address_hits("", text)]
 
     def test_no_dns_hostname_addresses_in_tests_tree(self):
         offenders = {}
         for path in sorted((config.ROOT / "tests").rglob("*.py")):
-            hits = [url for url in self._dns_addresses(
-                        path.read_text(encoding="utf-8"))
-                    if (path.name, self._host_of(url)) not in self._EXCEPTIONS]
+            hits = [url for _line, url in guard.network_address_hits(
+                        path.name, path.read_text(encoding="utf-8"))]
             if hits:
                 offenders[str(path.relative_to(config.ROOT))] = hits
         self.assertEqual(
```

## Предложения системе
- `orchestrator/advance_gates/refusal_classes.py`: у нового рубежа адресов
  `in_dev` нет своего действия класса «чинит роль» — модуль вне зон
  задачи, пришлось взять общее «переход отклонён». Стоит завести
  `"переход отклонён: сетевой адрес в tests/"` -> `ROLE_FIXES` и сменить
  `tests_writing.NETWORK_ADDRESS_ACTION` (класс «гейт добавлен — перечень
  классов в зону SPEC не попал»).
- Песочницы `tests/sandbox.py` отдают `gitcmd.diff_base` пустой строкой,
  а не `None`: гейт с проверкой `if base` вместо `base is None` тихо
  ломает чужие сценарии `in_dev -> verifying` (поймано на шаге этой
  задачи) — идиому стоит записать рядом с `gitcmd.diff_base`.
- `orchestrator/amend.py:510`: `amend-tests` зовёт
  `guard.long_lived_errors_from_files` без `network_addresses` — признак
  адресов инварианта 35 действует и у чужого проекта. Передать
  `network_addresses=repo_context.is_artel(target)` (файл вне зон этой
  задачи, был «только для чтения» ТЗ).
