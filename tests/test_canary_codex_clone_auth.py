"""Юнит-тесты входа Codex в эфемерном клоне канарейки (SPEC
01M3HST1381E1FZCYAN2TSB1F3): перечень ролей прогона, идущих провайдером
Codex, отказ по указателю связки ключей ДО клона, копия указателя в дом
роли клона, отказ по неподтверждённому входу и прокладка `codex_auth` через
фазу 1.

Каталог моделей, карта исполнителей и локальный слой — временные файлы под
патчами `config`: фикстуры (`_SetLayersTest`, `sets_block`, `SET_NAME`)
берутся из `tests/test_canary_sets.py`, потому что предмет здесь — надстройка
над ТЕМ ЖЕ разбором набора, и вторая копия карты ролей разошлась бы с первой
молча. Боевые `models.yaml`/`roles.yaml` не читаются: они крутилки Оператора,
и тест, опирающийся на их сегодняшнее содержимое, краснел бы от правки, к его
предмету отношения не имеющей.

Живой Codex CLI не запускается ни в одном тесте: там, где предмет — реакция
на исход проверки входа, подменяется сам узел `doctor.check_codex_chatgpt_
auth`; эфемерного клона здесь не заводится вовсе (настоящий клон с настоящим
холодным стартом — предмет приёмочной планки задачи).
"""
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import canary, config, doctor  # noqa: E402
from orchestrator.providers import codex as codex_provider  # noqa: E402
from tests.test_canary import pristine_config  # noqa: E402
from tests.test_canary_sets import (SET_NAME, _SetLayersTest,  # noqa: E402
                                    sets_block)

#: Модель раздела `codex` фикстурного каталога и модель раздела `claude` —
#: обе из `tests/test_canary_sets.py::CATALOG_TEXT`.
CODEX_MODEL = "model-codex-a"
CLAUDE_MODEL = "model-claude"

#: Роли яруса `strong` фикстурной карты исполнителей: `developer`/`reviewer`
#: набор называет, `analyst` — их сосед по ярусу, набором НЕ названный.
STRONG_ROLES = ("analyst", "developer", "reviewer")

#: Байты указателя-фикстуры: непустые и уникальные, чтобы равенство
#: байт-в-байт нельзя было получить пустым файлом.
POINTER_BYTES = b"bplist00\xd1\x01\x02keychain-pointer-fixture\n"


class _RoleHomeTest(_SetLayersTest):
    """`_SetLayersTest` + `config.ROLE_HOME` во временном каталоге: указатель
    живёт внутри дома роли, и без своего `ROLE_HOME` тест писал бы в дом роли
    машины."""

    def setUp(self):
        super().setUp()
        self.home = self.tdir / "home"
        self.home.mkdir()
        patcher = mock.patch.object(config, "ROLE_HOME", self.home)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pointer = self.home / canary._KEYCHAIN_POINTER_REL

    def write_pointer(self, payload: bytes = POINTER_BYTES) -> None:
        self.pointer.parent.mkdir(parents=True, exist_ok=True)
        self.pointer.write_bytes(payload)

    def plan(self, *entries: tuple) -> canary.CanarySetPlan:
        self.write_local(sets_block(*entries))
        return canary._set_plan(SET_NAME)


class CodexRolesOfPlanTest(_SetLayersTest):
    """Требование 2: роли прогона, идущие провайдером Codex."""

    def plan(self, *entries: tuple) -> canary.CanarySetPlan:
        self.write_local(sets_block(*entries))
        return canary._set_plan(SET_NAME)

    def test_every_role_of_the_shifted_tier_counts_not_only_the_named_ones(self):
        """Набор называет две роли яруса `strong`, а в перечне — все три
        роли этого яруса, по алфавиту.

        Ловит мутацию: перечень считается по записям набора
        (`plan.entries`) вместо ролей сдвинутого яруса (`_roles_of_tiers`) —
        роль-сосед по ярусу, которая на прогоне тоже идёт моделью и
        провайдером набора, в счёт не шла бы, и аргументом проверки входа
        стала бы не первая по алфавиту роль прогона (`analyst`), а
        `developer`: строка отказа перестала бы быть воспроизводимой.
        """
        plan = self.plan(("developer", "codex", CODEX_MODEL),
                         ("reviewer", "codex", CODEX_MODEL))

        self.assertEqual(STRONG_ROLES, plan.codex_roles)

    def test_a_set_on_the_default_provider_yields_no_codex_roles(self):
        """Набор на модели провайдера по умолчанию перечня ролей Codex не
        даёт вовсе.

        Ловит мутацию: перечень заполняется всяким НАЗВАННЫМ набором (то
        есть условие переноса записано как «передан `--set`») — набор на
        моделях Claude тоже получал бы указатель Оператора в дом клона и
        проверку входа Codex, то есть прогон отказывал бы там, где до
        задачи проходил.
        """
        plan = self.plan(("developer", "claude", CLAUDE_MODEL))

        self.assertEqual((), plan.codex_roles)

    def test_only_the_codex_tier_counts_when_the_set_shifts_two_tiers(self):
        """Набор сдвигает два яруса — на Codex и на провайдера по умолчанию;
        в перечне только роли яруса Codex, роль второго яруса в него не
        попадает.

        Ловит мутацию: перечень собирается по всем ролям сдвинутых ярусов
        без сверки провайдера их модели — роль на Claude считалась бы
        идущей провайдером Codex, и первой по алфавиту (аргументом проверки
        входа) могла бы стать роль, у которой дома Codex нет вовсе.
        """
        plan = self.plan(("developer", "codex", CODEX_MODEL),
                         ("writer", "claude", CLAUDE_MODEL))

        self.assertEqual(STRONG_ROLES, plan.codex_roles)

    def test_the_default_set_plan_carries_no_codex_roles(self):
        """План набора ПО УМОЛЧАНИЮ перечня ролей Codex не несёт.

        Ловит мутацию: у плана по умолчанию поле оставлено `None` вместо
        пустого кортежа — `_codex_clone_auth` на прогоне без `--set`
        свалился бы `TypeError` на `plan.codex_roles[0]` вместо тихого
        `None`, то есть самый частый прогон пульта перестал бы работать.
        """
        plan = canary._set_plan(config.CANARY_DEFAULT_SET)

        self.assertEqual((), plan.codex_roles)


class CodexCloneAuthTest(_RoleHomeTest):
    """Требование 3: отказ по указателю связки ключей ДО клона."""

    def codex_plan(self) -> canary.CanarySetPlan:
        return self.plan(("developer", "codex", CODEX_MODEL))

    def test_no_codex_role_means_no_auth_and_no_pointer_lookup(self):
        """Набор без ролей Codex даёт `None`, и указателя в доме роли пульта
        при этом нет вовсе — то есть его никто не спрашивал.

        Ловит мутацию: указатель читается до сверки перечня ролей — пульт,
        Codex не использующий, потерял бы команду `canary` целиком, потому
        что указателя связки ключей у него нет и не нужно.
        """
        plan = self.plan(("developer", "claude", CLAUDE_MODEL))
        self.assertFalse(self.pointer.exists(), "предпосылка: указателя нет")

        self.assertIsNone(canary._codex_clone_auth(plan))

    def test_the_pointer_bytes_and_the_first_role_alphabetically_are_returned(self):
        """Указатель на месте — возвращаются его БАЙТЫ и первая по алфавиту
        роль прогона, идущая провайдером Codex.

        Ловит мутацию: в клон уезжает ПУТЬ указателя, а не его байты —
        внутри блока клона тот же путь читался бы уже от переадресованного
        `ROLE_HOME`, то есть из дома роли клона, где указателя ещё нет, и
        копия вышла бы пустой либо отказала бы там, где отказывать поздно.
        """
        self.write_pointer()

        auth = canary._codex_clone_auth(self.codex_plan())

        self.assertEqual(POINTER_BYTES, auth.pointer)
        self.assertEqual(STRONG_ROLES[0], auth.role)

    def test_a_missing_pointer_is_refused_by_path_and_with_the_recipe(self):
        """Указателя нет — `SystemExit`, называющий путь, имя провайдера,
        роли прогона и рецепт двух однократных шагов Оператора.

        Ловит мутацию: отказ собран своим текстом без рецепта (или без
        пути) — Оператор получил бы «вход не найден» без указания, какой
        файл поставить и какой командой, то есть ровно ту непочинябельную
        строку, ради устранения которой отказ и заводится.
        """
        plan = self.codex_plan()

        with self.assertRaises(SystemExit) as ctx:
            canary._codex_clone_auth(plan)

        message = str(ctx.exception)
        self.assertIn(str(self.pointer), message)
        self.assertIn(codex_provider.CLI_NAME, message)
        self.assertIn(STRONG_ROLES[0], message)
        self.assertIn(doctor.CODEX_AUTH_RECIPE, message)

    def test_an_unreadable_pointer_is_refused_the_same_way(self):
        """Указатель существует, но не читается (каталог на его месте) — тот
        же именованный отказ с путём и рецептом.

        Ловит мутацию: читаемость проверяется `exists()`/`is_file()` вместо
        попытки чтения — нечитаемый указатель прошёл бы отказ до клона и
        свалился бы уже ВНУТРИ блока клона, то есть после `git clone`, а
        причина умерла бы вместе с уничтоженным клоном.
        """
        self.pointer.mkdir(parents=True)

        with self.assertRaises(SystemExit) as ctx:
            canary._codex_clone_auth(self.codex_plan())

        message = str(ctx.exception)
        self.assertIn(str(self.pointer), message)
        self.assertIn(doctor.CODEX_AUTH_RECIPE, message)


class InstallCodexPointerTest(_RoleHomeTest):
    """Требования 1 и 5: копия РОВНО одного файла в дом роли клона."""

    def files_under_home(self) -> set:
        return {str(path.relative_to(self.home))
                for path in self.home.rglob("*") if path.is_file()}

    def test_exactly_one_file_appears_at_the_same_relative_path(self):
        """В доме роли появляется ровно один файл — указатель тем же
        относительным путём и байт-в-байт, вместе с недостающими
        каталогами.

        Ловит мутацию: копия положена в корень дома роли (или рядом с ним)
        вместо `Library/Preferences/` — `codex login status` искал бы
        указатель по своему адресу `$HOME/Library/Preferences`, не нашёл бы
        его и остался бы без входа при исправно «перенесённом» файле.
        """
        canary._install_codex_pointer(POINTER_BYTES)

        self.assertEqual({str(canary._KEYCHAIN_POINTER_REL)},
                         self.files_under_home())
        self.assertEqual(POINTER_BYTES, self.pointer.read_bytes())

    def test_an_existing_pointer_is_overwritten_not_appended(self):
        """Указатель на месте — он перезаписывается байтами копии, а не
        дописывается.

        Ловит мутацию: файл открывается на дозапись — указатель клона стал
        бы склейкой двух plist'ов, то есть перестал бы разбираться вовсе, и
        `codex login status` домом клона не нашёл бы связку при внешне
        успешном переносе.
        """
        self.write_pointer(b"staroe soderzhimoe\n")

        canary._install_codex_pointer(POINTER_BYTES)

        self.assertEqual(POINTER_BYTES, self.pointer.read_bytes())


class RefuseUnlessCloneLoggedInTest(unittest.TestCase):
    """Требование 4 (01M3HST1381E1FZCYAN2TSB1F3): реакция прогона на исход
    проверки входа — и требование 6 (01M3M55070T5NJFYM3QQJH4B9V):
    различение двух её отказов.

    Узел `doctor.check_codex_chatgpt_auth` подменён: предмет здесь — что
    прогон делает с его исходом, а сам узел и его разбор вывода CLI —
    предмет `tests/test_doctor.py`. Различитель подмены — `config.ROLE_HOME`
    в момент вызова: именно от него настоящий узел берёт `HOME` процесса
    `codex login status`, и «вход домом роли пульта» отличается от
    «проверки окружением шага клона» ровно этим значением.
    """

    ROLE = "developer"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        self.pult_home = self.tdir / "pult-home"
        self.clone_home = self.tdir / "clone-home"
        patcher = mock.patch.object(config, "ROLE_HOME", self.clone_home)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(codex_provider.set_codex_home_override,
                        codex_provider.codex_home_override())
        codex_provider.set_codex_home_override(
            self.pult_home / codex_provider.DEPLOYED_HOME_DIR)
        #: (дом роли, переопределение `CODEX_HOME`) каждого вызова узла.
        self.calls = []

    def check(self, status: str) -> doctor.Check:
        return doctor.Check(doctor.CODEX_AUTH_CHECK, status,
                            f"роль {self.ROLE}: {doctor.CODEX_AUTH_RECIPE}")

    def node(self, *, pult: str, clone: str):
        """Подмена узла: исход зависит от дома роли, каким его зовут."""
        def fake(role):
            self.calls.append((config.ROLE_HOME,
                               codex_provider.codex_home_override()))
            return self.check(
                pult if config.ROLE_HOME == self.pult_home else clone)
        return mock.patch.object(doctor, "check_codex_chatgpt_auth", fake)

    def refusal(self, *, pult: str, clone: str) -> str:
        with self.node(pult=pult, clone=clone):
            with self.assertRaises(SystemExit) as ctx:
                canary._refuse_unless_clone_logged_in(self.ROLE,
                                                      self.pult_home)
        return str(ctx.exception)

    def refuse(self, status: str) -> str:
        """Текст отказа, когда узел отвечает `status` ОБОИМ домам."""
        return self.refusal(pult=status, clone=status)

    def test_a_failed_check_refuses_naming_the_check_and_its_detail(self):
        """Исход `fail` — `SystemExit` с именем проверки и её `detail`
        целиком.

        Ловит мутацию: результат проверки собран, но не влияет на ход
        прогона (записан в отчёт и забыт) — прогон тратил бы шаг роли на
        заведомо неавторизованном доме, то есть платил бы ровно тем
        падением авторизации, ради устранения которого проверка и
        заводится.
        """
        message = self.refuse("fail")

        self.assertIn(doctor.CODEX_AUTH_CHECK, message)
        self.assertIn(doctor.CODEX_AUTH_RECIPE, message)

    def test_a_warning_is_refused_too_not_only_a_failure(self):
        """Исход `warn` — тоже отказ: `ok` и «не `ok`» различаются, а не
        «`fail` и всё остальное».

        Ловит мутацию: условие записано как `status == "fail"` — любой
        новый неуспешный исход узла (жёлтая строка вместо красной) молча
        уводил бы прогон на шаг роли с неподтверждённым входом.
        """
        self.assertIn(doctor.CODEX_AUTH_CHECK, self.refuse("warn"))

    def test_a_confirmed_login_lets_the_run_continue_silently(self):
        """Исход `ok` — ни отказа, ни вывода: прогон продолжается.

        Ловит мутацию: отказ поставлен на сам факт вызова проверки (или
        исход трактуется наоборот) — прогон на наборе с Codex был бы
        невозможен вообще, при любом состоянии входа.
        """
        with self.node(pult="fail", clone="ok"):
            self.assertIsNone(
                canary._refuse_unless_clone_logged_in(self.ROLE,
                                                      self.pult_home))

    def test_a_confirmed_login_asks_the_node_exactly_once(self):
        """Проверка окружением шага клона прошла — узел спрошен ровно
        один раз, как до различения двух случаев.

        Ловит мутацию: вход домом роли пульта спрашивается ДО проверки
        окружением шага (или безусловно рядом с ней) — каждый прогон на
        наборе с ролями Codex платил бы вторым запуском `codex login
        status`, а тот при `keyring` обращается к связке ключей и вправе
        спросить у Оператора разрешение: лишний вызов не бесплатный, он
        может и повиснуть до потолка ожидания.
        """
        with self.node(pult="ok", clone="ok"):
            canary._refuse_unless_clone_logged_in(self.ROLE, self.pult_home)

        self.assertEqual(1, len(self.calls))

    def test_a_confirmed_pult_login_names_a_pult_defect_without_the_recipe(self):
        """Вход домом роли пульта подтверждён, а проверка окружением шага
        клона — нет: отказ БЕЗ рецепта, не равный отказу несделанного
        входа, называющий сломанный перенос и путь, который шагу
        отдаётся.

        Ловит мутацию: различение не сделано — оба исхода пересказываются
        одним текстом с рецептом `codex login`; Оператор, у которого вход
        есть, получал бы указание войти ещё раз, а настоящая причина
        (перенос `CODEX_HOME` в клон сломан) оставалась бы неназванной и
        искалась бы руками.
        """
        defect = self.refusal(pult="ok", clone="fail")

        self.assertNotIn(doctor.CODEX_AUTH_RECIPE, defect)
        self.assertNotEqual(self.refuse("fail"), defect)
        self.assertIn(
            str(self.pult_home / codex_provider.DEPLOYED_HOME_DIR), defect)

    def test_the_pult_probe_asks_with_the_pult_home_and_no_override(self):
        """Второй вызов узла идёт домом роли ПУЛЬТА и со снятым
        переопределением `CODEX_HOME`, а после него оба значения снова
        клоновские.

        Ловит мутацию: вход пульта спрашивается, не сняв переопределение
        (или не вернув `config.ROLE_HOME`) — узел получал бы гибрид
        «`HOME` клона + `CODEX_HOME` пульта», то есть ровно то окружение,
        неуспех которого и разбирается: ответ был бы тем же `fail`, и
        дефект пульта навсегда пересказывался бы рецептом «войдите».
        """
        override = codex_provider.codex_home_override()

        self.refusal(pult="ok", clone="fail")

        self.assertEqual([(self.clone_home, override),
                          (self.pult_home, None)], self.calls)
        self.assertEqual(self.clone_home, config.ROLE_HOME)
        self.assertEqual(override, codex_provider.codex_home_override())

    def test_the_pult_probe_restores_the_clone_paths_when_the_node_raises(self):
        """Узел упал исключением на втором вызове — дом роли и
        переопределение всё равно вернулись клоновскими.

        Ловит мутацию: возврат написан последней строкой после вызова, а
        не в `finally` — упавший второй вызов оставил бы блок клона с
        путями ПУЛЬТА, и уборка клона (`shutil.rmtree` по `dest`) с
        восстановлением `config` пошли бы от подменённых значений.
        """
        override = codex_provider.codex_home_override()

        def boom(role):
            raise RuntimeError("узел упал на доме роли пульта")

        with mock.patch.object(doctor, "check_codex_chatgpt_auth", boom):
            with self.assertRaises(RuntimeError):
                canary._pult_home_login_confirmed(self.ROLE, self.pult_home)

        self.assertEqual(self.clone_home, config.ROLE_HOME)
        self.assertEqual(override, codex_provider.codex_home_override())


class EphemeralCloneCodexHomeTest(unittest.TestCase):
    """Требования 1, 4 (01M3M55070T5NJFYM3QQJH4B9V): шов блока эфемерного
    клона — постановка переопределения `CODEX_HOME` и его снятие.

    Настоящего git здесь нет (`git clone` заводит каталог, остальные
    команды отвечают нулём, холодный старт заглушен) — тем же приёмом, что
    `tests/test_canary.py::EphemeralCloneConfigRemapTest`. Настоящий
    клиент Codex не запускается и связка ключей не спрашивается: узел
    проверки входа подменён исходом `ok`.
    """

    ROLE = "analyst"

    def setUp(self):
        pristine = pristine_config()
        self.suffixes = {
            attr: getattr(pristine, attr).relative_to(pristine.ROOT)
            for attr in canary._CLONE_CONFIG_ATTRS}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        self.outer_root = self.tdir / "outer"
        self.outer_root.mkdir()
        for attr in canary._CLONE_CONFIG_ATTRS:
            patcher = mock.patch.object(config, attr,
                                        self.outer_root / self.suffixes[attr])
            patcher.start()
            self.addCleanup(patcher.stop)
        self.pult_role_home = config.ROLE_HOME
        self.addCleanup(codex_provider.set_codex_home_override,
                        codex_provider.codex_home_override())
        codex_provider.set_codex_home_override(None)

    def auth(self) -> canary.CodexCloneAuth:
        return canary.CodexCloneAuth(self.ROLE, POINTER_BYTES)

    @contextmanager
    def fake_clone(self):
        """`_ephemeral_clone` без настоящего git и с подтверждённым
        входом."""
        def fake_run(cmd, **_kw):
            if list(cmd[:2]) == ["git", "clone"]:
                Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        def logged_in(role):
            return doctor.Check(doctor.CODEX_AUTH_CHECK, "ok",
                                f"роль {role}: вход подтверждён")

        with mock.patch.object(canary.tempfile, "mkdtemp",
                               side_effect=self._mkdtemp), \
             mock.patch.object(canary.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(canary.catalog, "cmd_init", lambda: None), \
             mock.patch.object(doctor, "check_codex_chatgpt_auth", logged_in):
            yield

    def _mkdtemp(self, prefix: str = "", **_kw) -> str:
        path = self.tdir / ("origin" if "origin" in prefix else "clone")
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def test_the_block_overrides_codex_home_with_the_pult_client_directory(self):
        """Внутри блока с входом Codex переопределение равно каталогу
        клиента дома роли ПУЛЬТА, а дом роли при этом — клоновский.

        Ловит мутацию: переопределение считается от `config.ROLE_HOME`
        внутри блока (то есть уже переадресованного) — оно совпало бы с
        каталогом клиента КЛОНА, механика выглядела бы сделанной и не
        меняла бы ровным счётом ничего.
        """
        with self.fake_clone():
            with canary._ephemeral_clone(codex_auth=self.auth()):
                inside = codex_provider.codex_home_override()
                clone_role_home = config.ROLE_HOME

        self.assertEqual(
            self.pult_role_home / codex_provider.DEPLOYED_HOME_DIR, inside)
        self.assertNotEqual(self.pult_role_home, clone_role_home)

    def test_a_block_without_codex_auth_sets_no_override(self):
        """Без входа Codex переопределения нет и внутри блока.

        Ловит мутацию: переопределение ставится на входе в блок
        безусловно, не по наличию входа Codex — шаг роли на прогоне без
        ролей Codex получал бы каталог клиента ПУЛЬТА, то есть прогон
        перестал бы проверять дом роли того sha, ради которого клон и
        заводится.
        """
        with self.fake_clone():
            with canary._ephemeral_clone(codex_auth=None):
                self.assertIsNone(codex_provider.codex_home_override())

    def test_the_override_is_dropped_on_both_exits_from_the_block(self):
        """Штатный выход и выход ИСКЛЮЧЕНИЕМ одинаково возвращают прежнее
        значение переопределения.

        Ловит мутацию: снятие написано последней строкой тела блока, а не
        в `finally` — упавший прогон канарейки (а падает он штатно:
        `git clone` не создан, checkout не удался) оставлял бы пультовский
        `CODEX_HOME` в окружении всех последующих боевых шагов процесса.
        """
        with self.fake_clone():
            with canary._ephemeral_clone(codex_auth=self.auth()):
                pass
            self.assertIsNone(codex_provider.codex_home_override())

            with self.assertRaises(ValueError):
                with canary._ephemeral_clone(codex_auth=self.auth()):
                    raise ValueError("боевой отказ внутри блока клона")

        self.assertIsNone(codex_provider.codex_home_override())


#: Метрики задачи, которых достаточно печати `_run_one_task` — фаза 1 в
#: тестах ниже подменена, и настоящих метрик взять негде.
FIXTURE_METRICS = {
    "steps": 3, "cost_usd": 1.0, "review_iterations": 0, "escalations": [],
    "dev_retries": 0, "outcome": "killed", "kill_note": "штатно",
    "test_author_visited": False, "ceiling_raise": None,
    "ceiling_exhausted": False,
}


class PhaseOneCodexAuthArgumentTest(unittest.TestCase):
    """Прокладка `codex_auth` до фазы 1 — и её обратная совместимость.

    Ни одного клона и ни одного обращения к БД: фаза 1 и обе фазы записи
    подменены, предмет — только аргументы вызова фазы 1.
    """

    def run_one_task(self, codex_auth, phase_one) -> None:
        with mock.patch.object(canary, "_run_task_in_ephemeral_clone",
                               phase_one), \
             mock.patch.object(canary.store, "db", lambda: None), \
             mock.patch.object(canary, "_record_canary_run",
                               lambda *a, **k: ("sha", "метка")), \
             mock.patch.object(canary, "_baseline_deviation_note",
                               lambda *a, **k: ""), \
             mock.patch("builtins.print", lambda *a, **k: None):
            canary._run_one_task(Path("template.md"), "20260927T000000Z", 0.5,
                                 codex_auth=codex_auth)

    def phase_one_of_five_parameters(self, seen: dict):
        """Фикстура фазы 1 с РОВНО пятью параметрами — той же подписью, что
        у залоченной планки 01M3GKJFN90ATK2KECNDZXPPP6."""
        def phase_one(template_path, run_stamp, explicit_target_sha,
                      outer_root, layer_text=None):
            seen["layer_text"] = layer_text
            return ("01M3HSTPLANKA0000000000001", "shablon", False, [],
                    FIXTURE_METRICS, False, False, True, None)
        return phase_one

    def test_phase_one_is_called_without_the_new_argument_when_there_is_none(self):
        """Без входа Codex фаза 1 зовётся ровно прежними пятью аргументами.

        Ловит мутацию: `codex_auth` передаётся фазе 1 безусловно — вызов
        уронил бы `TypeError` любую подмену фазы 1 с прежней подписью
        (залоченная планка 01M3GKJFN90ATK2KECNDZXPPP6 подменяет её
        фикстурой ровно пяти параметров), причём и на наборе по умолчанию,
        где никакого входа Codex нет вовсе.
        """
        seen = {}

        self.run_one_task(None, self.phase_one_of_five_parameters(seen))

        self.assertEqual({"layer_text": None}, seen)

    def test_phase_one_receives_the_auth_when_there_is_one(self):
        """С входом Codex фаза 1 получает его именованным аргументом.

        Ловит мутацию: `codex_auth` до фазы 1 не доезжает (собран в
        `cmd_canary` и потерян) — указатель в дом роли клона не попадал бы,
        а проверка входа не звалась бы: механика выглядела бы сделанной и
        не делала бы ничего.
        """
        auth = canary.CodexCloneAuth("analyst", POINTER_BYTES)
        seen = {}

        def phase_one(template_path, run_stamp, explicit_target_sha,
                      outer_root, layer_text=None, codex_auth=None):
            seen["codex_auth"] = codex_auth
            return ("01M3HSTPLANKA0000000000002", "shablon", False, [],
                    FIXTURE_METRICS, False, False, True, None)

        self.run_one_task(auth, phase_one)

        self.assertEqual({"codex_auth": auth}, seen)


if __name__ == "__main__":
    unittest.main()
