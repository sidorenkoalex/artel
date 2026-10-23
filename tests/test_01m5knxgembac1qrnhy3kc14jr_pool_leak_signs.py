"""Признаки утечки пула канарейки в логах шагов ролей:
`doctor.check_role_log_pool_leak` после сужения признака (поправка
Оператора к ADR-0017 от 23.10.2026, вариант Б).

Группа: долгоживущий
Красен до реализации: проверка считает утечкой голую подстроку каталога пула — «не признаки» AC-1/AC-2 дают `fail`, GUID шаблона (AC-5) не ловится, деталей «GUID шаблонов не сверялись» (AC-6/AC-7) и предупреждения о шаблоне без метки (AC-8) нет.

Свойство — чистое поведение одной проверки над каталогом логов и
открытым пулом: функция зовётся напрямую, `Path.home` подменён временным
каталогом, `config.ROOT`/`config.DB`/`config.LOGS` — песочницей,
`doctor.runner.in_role_environment` — явным значением режима. Образцы
утечки собираются во время прогона из `config.CANARY_POOL_DIRNAME` и
`TOOL_CALL_LINE_PREFIX` провайдера, а имена логов и значения меток GUID —
модулем `random`; зерно печатается и входит в текст провала.
"""
import builtins
import random
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from orchestrator import alerts, config, doctor, store
from orchestrator.providers.claude import TOOL_CALL_LINE_PREFIX

DETAIL_GUID_KIND = "GUID шаблона пула канарейки"
DETAIL_ROLE_PROCESS = "GUID шаблонов не сверялись: процесс роли"
DETAIL_POOL_ABSENT = "GUID шаблонов не сверялись: открытый пул не развёрнут"


def legacy_alert_text(log_name: str) -> str:
    """Прежний побайтно текст алерта признаков 1а, 1б, 1г."""
    return (f"лог роли {log_name} упоминает каталог пула канарейки "
            f"({config.CANARY_POOL_DIRNAME}) — утечка контекста роли (SPEC "
            f"01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 13б)")


class PoolLeakSignsTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("LOGS", self.root / ".artel" / "logs")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()
        config.LOGS.mkdir(parents=True)

        home_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(home_tmp.cleanup)
        self.home = Path(home_tmp.name)
        home_patcher = mock.patch.object(Path, "home", return_value=self.home)
        home_patcher.start()
        self.addCleanup(home_patcher.stop)
        self.pool = self.home / config.CANARY_POOL_DIRNAME

        self.role_env = False
        role_patcher = mock.patch.object(
            doctor.runner, "in_role_environment",
            side_effect=lambda *a, **k: self.role_env)
        role_patcher.start()
        self.addCleanup(role_patcher.stop)

    # --- помощники сценария -------------------------------------------

    def why(self, extra: str = "") -> str:
        return f"зерно: {self.seed}; {extra}"

    def guid(self) -> str:
        return str(uuid.UUID(int=self.rng.getrandbits(128)))

    def log_name(self) -> str:
        task = "".join(self.rng.choice("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
                       for _ in range(26))
        role = self.rng.choice(("developer", "test_author", "reviewer",
                                "spec_auditor"))
        return f"{task}-{role}-{self.rng.randint(1, 9)}.log"

    def tag(self, value: str) -> str:
        return self.rng.choice((f"<!-- canary-guid: {value} -->",
                                f"canary-guid: {value}"))

    def template(self, name: str, *values: str) -> str:
        """Шаблон открытого пула с метками `values`; тело — уникальное."""
        self.pool.mkdir(exist_ok=True)
        body = f"тело шаблона {self.guid()}"
        lines = [f"# {name}"]
        for value in values:
            lines += [self.tag(value), body]
        if not values:
            lines.append(body)
        (self.pool / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return body

    def tagged_pool(self) -> str:
        """Развёрнутый пул с одним помеченным шаблоном; значение метки."""
        value = self.guid()
        self.template("alpha.md", value)
        return value

    def write_log(self, *lines: str) -> str:
        """Единственный лог шага роли каталога логов; прежние убираются."""
        for old in config.LOGS.glob("*.log"):
            old.unlink()
        name = self.log_name()
        (config.LOGS / name).write_text(
            "Agent: начинаю шаг\n" + "\n".join(lines) + "\nготово\n",
            encoding="utf-8")
        return name

    def run_check(self):
        return doctor.check_role_log_pool_leak(self.conn)

    def incidents(self) -> list:
        return [a for a in alerts.open_alerts(self.conn, "incident")
                if a["source"] == "doctor.canary-pool-leak"]

    # --- AC-1 ---------------------------------------------------------

    def test_ac1_non_sign_lines_are_ok_without_alerts(self):
        """Лог из одних «не признаков» требования 1 — `ok`, алертов нет.

        Пул развёрнут и помечен (сверка GUID идёт), лог несёт строку
        константы, упоминания каталога в обратных кавычках и в правиле
        `Read(...)`, дом Codex от `~/` и от абсолютного дома, одноимённый
        каталог вне дома, слово `canary-guid:` без значения из пула и
        строку вызова с префиксом не в начале строки. Каждая строка
        проверяется отдельным логом и все вместе — одним.

        Ловит мутацию: признак остаётся голой подстрокой каталога
        (`marker in text`) либо префикс вызова ищется в любом месте строки,
        а не в её начале, — проверка даёт `fail` и поднимает алерт.
        """
        self.tagged_pool()
        d = config.CANARY_POOL_DIRNAME
        lines = [
            f'CANARY_POOL_DIRNAME = "{d}"',
            f"`~/{d}`",
            f"`~/{d}/*.md`",
            f"Read(~/{d}/**)",
            f"~/{d}-codex/auth.json",
            f"/x/.artel/worktrees/T1/{d}/y.py",
            "canary-guid:",
            f"canary-guid: {self.guid()}",
            f"текст {TOOL_CALL_LINE_PREFIX}Bash ls ~/{d}",
            f"{Path.home()}/{d}-codex/auth.json",
        ]
        for line in lines:
            with self.subTest(line=line):
                before = len(self.incidents())
                name = self.write_log(line)
                check = self.run_check()
                self.assertEqual(check.status, "ok",
                                 self.why(f"{name}: {check.detail}"))
                self.assertEqual(len(self.incidents()), before, self.why(line))
        shuffled = lines[:]
        self.rng.shuffle(shuffled)
        before = len(self.incidents())
        name = self.write_log(*shuffled)
        check = self.run_check()
        self.assertEqual(check.status, "ok", self.why(f"{name}: {check.detail}"))
        self.assertEqual(len(self.incidents()), before,
                         self.why("все строки разом"))
        self.assertEqual(self.incidents(), [], self.why("алерты по ходу"))

    # --- AC-2 ---------------------------------------------------------

    def test_ac2_codex_home_in_tool_call_is_ok(self):
        """Строка вызова `· Bash cat ~/<каталог>-codex/auth.json` — `ok`.

        Ловит мутацию: признак 1г берёт каталог пула в строке вызова без
        границы справа (подстрока без проверки следующего знака) — дом
        Codex канарейки в строке вызова даёт `fail` и алерт.
        """
        self.tagged_pool()
        d = config.CANARY_POOL_DIRNAME
        for tool, args in (("Bash", f"cat ~/{d}-codex/auth.json"),
                           ("Read", f"~/{d}-codex/config.toml")):
            with self.subTest(tool=tool):
                name = self.write_log(f"{TOOL_CALL_LINE_PREFIX}{tool} {args}")
                check = self.run_check()
                self.assertEqual(check.status, "ok",
                                 self.why(f"{name}: {check.detail}"))
                self.assertEqual(self.incidents(), [], self.why(args))

    # --- AC-3 ---------------------------------------------------------

    def test_ac3_bare_dir_in_tool_call_fails_with_legacy_alert(self):
        """`<префикс>Bash ls ~/<каталог>` с концом строки — `fail` и один
        алерт прежнего текста; та же команда без префикса — `ok`.

        Ловит мутацию: признак 1г выброшен (в строке вызова ловится только
        путь внутри пула 1а) — голый каталог в вызове проходит `ok`; либо
        текст алерта 1г переписан — дедупликация с открытыми алертами
        ломается, и сверка побайтно краснеет.
        """
        self.tagged_pool()
        d = config.CANARY_POOL_DIRNAME
        name = self.write_log(f"{TOOL_CALL_LINE_PREFIX}Bash ls ~/{d}")
        check = self.run_check()
        self.assertEqual(check.status, "fail", self.why(check.detail))
        incidents = self.incidents()
        self.assertEqual(len(incidents), 1, self.why(str(incidents)))
        self.assertEqual(incidents[0]["kind"], "incident")
        self.assertEqual(incidents[0]["message"], legacy_alert_text(name),
                         self.why())
        name = self.write_log(f"ls ~/{d}")
        before = len(alerts.open_alerts(self.conn, "incident"))
        check = self.run_check()
        self.assertEqual(check.status, "ok", self.why(f"{name}: {check.detail}"))
        self.assertEqual(len(alerts.open_alerts(self.conn, "incident")), before,
                         self.why("алерт без префикса вызова"))

    # --- AC-4 ---------------------------------------------------------

    def test_ac4_home_path_forms_fail_with_legacy_alert(self):
        """Четыре формы пути пула вне строк вызова — `fail` и прежний текст.

        Абсолютный каталог пула с пробелом после, путь внутри пула от
        `str(Path.home())`, `$HOME/` и `${HOME}/` — каждая отдельным логом.

        Ловит мутацию: признак 1а знает только префикс `~/` (без
        `$HOME/`, `${HOME}/` и абсолютного дома) либо признак 1б пропущен —
        соответствующая форма проходит `ok` без алерта.
        """
        self.tagged_pool()
        d = config.CANARY_POOL_DIRNAME
        home = str(Path.home())
        forms = [
            f"смотрю {Path.home() / d} дальше",
            f"{home}/{d}/x.md",
            f"$HOME/{d}/x.md",
            "${HOME}/" + d + "/x.md",
        ]
        for form in forms:
            with self.subTest(form=form):
                name = self.write_log(form)
                check = self.run_check()
                self.assertEqual(check.status, "fail",
                                 self.why(f"{form}: {check.detail}"))
                messages = [a["message"] for a in self.incidents()]
                self.assertIn(legacy_alert_text(name), messages, self.why(form))

    # --- AC-5 ---------------------------------------------------------

    def test_ac5_template_guid_in_log_fails_without_revealing_value(self):
        """Значение метки шаблона в логе без каталога пула — `fail`, один
        алерт; значения нет ни в алерте, ни в детали.

        Деталь называет файл лога и вид признака, текст алерта — каталог
        пула. Два прогона над тем же логом оставляют один открытый алерт.

        Ловит мутацию: признак 1в не реализован (GUID шаблонов не
        читаются) — лог проходит `ok`; либо значение GUID подставлено в
        текст алерта/детали — утверждение «значения нет» краснеет; либо в
        текст алерта 1в вписано изменчивое (время, счётчик) — второй
        прогон заводит второй алерт.
        """
        value = self.tagged_pool()
        name = self.write_log(f"шаблон помечен {value} — читаю дальше")
        check = self.run_check()
        self.assertEqual(check.status, "fail", self.why(check.detail))
        incidents = self.incidents()
        self.assertEqual(len(incidents), 1, self.why(str(incidents)))
        self.assertEqual(incidents[0]["kind"], "incident")
        message = incidents[0]["message"]
        self.assertNotIn(value, message, self.why())
        self.assertIn(config.CANARY_POOL_DIRNAME, message, self.why())
        self.assertNotIn(value, check.detail, self.why())
        self.assertIn(name, check.detail, self.why())
        self.assertIn(DETAIL_GUID_KIND, check.detail, self.why())

        self.run_check()
        self.assertEqual(len(self.incidents()), 1,
                         self.why("второй прогон над тем же логом"))

    def test_ac5_guid_and_home_path_raise_two_alerts(self):
        """Лог со значением GUID и путём внутри пула поднимает два алерта.

        Ловит мутацию: признаки проверяются по `elif` — первое же
        срабатывание глушит второй признак, и алерт остаётся один.
        """
        value = self.tagged_pool()
        d = config.CANARY_POOL_DIRNAME
        name = self.write_log(f"метка {value}", f"Agent: читаю ~/{d}/x.md")
        check = self.run_check()
        self.assertEqual(check.status, "fail", self.why(check.detail))
        incidents = self.incidents()
        self.assertEqual(len(incidents), 2, self.why(str(incidents)))
        self.assertIn(legacy_alert_text(name),
                      [a["message"] for a in incidents], self.why())
        for alert in incidents:
            self.assertNotIn(value, alert["message"], self.why())

    def test_ac5_any_template_and_any_tag_counts(self):
        """Значение метки второго шаблона и второй метки шаблона — `fail`.

        Ловит мутацию: читается только первый шаблон пула или только первая
        метка шаблона (`re.search` вместо перебора всех совпадений) —
        значение второй метки проходит `ok`.
        """
        first, second = self.guid(), self.guid()
        self.template("alpha.md", first)
        self.template("beta.md", second)
        name = self.write_log(f"метка {second}")
        check = self.run_check()
        self.assertEqual(check.status, "fail",
                         self.why(f"второй шаблон, {name}: {check.detail}"))

        for old in self.pool.glob("*.md"):
            old.unlink()
        one, two = self.guid(), self.guid()
        self.template("gamma.md", one, two)
        name = self.write_log(f"метка {two}")
        check = self.run_check()
        self.assertEqual(check.status, "fail",
                         self.why(f"вторая метка, {name}: {check.detail}"))

    # --- AC-6 ---------------------------------------------------------

    def read_spy(self):
        """(имена прочитанных `*.md` пула, стек слежки за чтением)."""
        seen = []
        pool = self.pool

        def note(target):
            try:
                path = Path(target)
            except TypeError:
                return
            if path.suffix == ".md" and path.parent == pool:
                seen.append(path.name)

        real_read_text, real_read_bytes = Path.read_text, Path.read_bytes
        real_path_open, real_open = Path.open, builtins.open

        def read_text(self_path, *args, **kwargs):
            note(self_path)
            return real_read_text(self_path, *args, **kwargs)

        def read_bytes(self_path, *args, **kwargs):
            note(self_path)
            return real_read_bytes(self_path, *args, **kwargs)

        def path_open(self_path, *args, **kwargs):
            note(self_path)
            return real_path_open(self_path, *args, **kwargs)

        def open_(file, *args, **kwargs):
            note(file)
            return real_open(file, *args, **kwargs)

        stack = mock.patch.multiple(Path, read_text=read_text,
                                    read_bytes=read_bytes, open=path_open)
        return seen, stack, mock.patch.object(builtins, "open", open_)

    def test_ac6_role_process_does_not_read_pool(self):
        """Под процессом роли файлы `*.md` пула не читаются, деталь
        называет причину; формы 1а от `~/`/`$HOME/`/`${HOME}/` и 1г — `fail`.

        Ловит мутацию: проверка `in_role_environment()` пропущена или
        стоит после чтения шаблонов — слежка видит чтение `alpha.md`; либо
        в режиме роли выключены все признаки, а не только 1в — формы 1а и
        1г проходят `ok`.
        """
        value = self.tagged_pool()
        self.role_env = True
        self.write_log(f"шаблон помечен {value} — читаю дальше")
        seen, path_spy, open_spy = self.read_spy()
        with path_spy, open_spy:
            check = self.run_check()
        self.assertEqual(seen, [], self.why("файлы пула прочитаны"))
        self.assertIn(DETAIL_ROLE_PROCESS, check.detail, self.why(check.detail))

        d = config.CANARY_POOL_DIRNAME
        forms = [
            f"~/{d}/x.md",
            f"$HOME/{d}/x.md",
            "${HOME}/" + d + "/x.md",
            f"{TOOL_CALL_LINE_PREFIX}Bash ls ~/{d}",
        ]
        for form in forms:
            with self.subTest(form=form):
                self.write_log(form)
                check = self.run_check()
                self.assertEqual(check.status, "fail",
                                 self.why(f"{form}: {check.detail}"))

    # --- AC-7 ---------------------------------------------------------

    def test_ac7_pool_absent_still_checks_paths(self):
        """Пул не развёрнут: признаки 1а и 1б дают `fail`, деталь
        называет «открытый пул не развёрнут».

        Ловит мутацию: отсутствие каталога пула обрывает проверку ранним
        `ok` (как отсутствие каталога логов) — путь внутри пула и
        абсолютный каталог пула проходят без срабатывания; либо деталь о
        несверенных GUID не добавлена.
        """
        self.assertFalse(self.pool.exists())
        d = config.CANARY_POOL_DIRNAME
        for form in (f"Agent: читаю ~/{d}/x.md",
                     f"смотрю {Path.home() / d} дальше"):
            with self.subTest(form=form):
                self.write_log(form)
                check = self.run_check()
                self.assertEqual(check.status, "fail",
                                 self.why(f"{form}: {check.detail}"))
                self.assertIn(DETAIL_POOL_ABSENT, check.detail,
                              self.why(check.detail))

    # --- AC-8 ---------------------------------------------------------

    def test_ac8_untagged_template_warns_by_name(self):
        """Шаблон без метки при чистых логах — `warn` с именем файла, без
        его текста и без алерта; при утечке в логах — `fail`.

        Ловит мутацию: шаблон без метки молча пропускается — статус `ok`;
        либо в деталь попадает содержимое шаблона; либо предупреждение
        перекрывает утечку — статус `warn` вместо `fail`.
        """
        self.tagged_pool()
        body = self.template("bare.md")
        self.write_log("Обычный шаг роли: правка кода, коммит.")
        check = self.run_check()
        self.assertEqual(check.status, "warn", self.why(check.detail))
        self.assertIn("bare.md", check.detail, self.why())
        self.assertNotIn(body, check.detail, self.why())
        self.assertEqual(self.incidents(), [], self.why())
        self.assertEqual(alerts.open_alerts(self.conn), [], self.why())

        self.write_log(f"Agent: читаю ~/{config.CANARY_POOL_DIRNAME}/x.md")
        check = self.run_check()
        self.assertEqual(check.status, "fail", self.why(check.detail))

    def test_ac8_empty_tag_is_untagged_and_matches_nothing(self):
        """Шаблон с единственной пустой меткой — `warn` с именем файла;
        лог без признаков 1а, 1б, 1г не даёт `fail` и алерта.

        Пустая метка: за `canary-guid:` сразу `-->`, перевод строки или
        конец текста. Лог несёт «-->», «canary-guid:» и обычный текст.

        Ловит мутацию: пустое значение или `-->` принято за значение метки
        — пустая строка входит в любой лог (или `-->` в лог с этим
        знаком), проверка даёт `fail` и алерт; либо шаблон с пустой меткой
        считается помеченным — `ok` вместо `warn`.
        """
        self.pool.mkdir()
        forms = ["# empty\n<!-- canary-guid: -->\nтело\n",
                 "# empty\n<!-- canary-guid:-->\nтело\n",
                 "# empty\ncanary-guid:\nтело\n",
                 "# empty\nтело\ncanary-guid:"]
        for text in forms:
            with self.subTest(template=text):
                (self.pool / "empty.md").write_text(text, encoding="utf-8")
                self.write_log("Обычный шаг роли.", "<!-- комментарий -->",
                               "canary-guid: -->", "canary-guid:",
                               f"строка {self.guid()}")
                check = self.run_check()
                self.assertEqual(check.status, "warn",
                                 self.why(f"{text!r}: {check.detail}"))
                self.assertIn("empty.md", check.detail, self.why())
                self.assertEqual(self.incidents(), [], self.why(repr(text)))


if __name__ == "__main__":
    unittest.main()
