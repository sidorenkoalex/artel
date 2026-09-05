"""AC-13, AC-14, AC-15 (SPEC.md, требование 5 «Изоляция») — расшифровка
пула недоступна ролям: запрет в курируемом слое, аудит вызова
incident-алертом, именованный отказ пульта в окружении роли.

AC-13: ANSWER-1 п.2 разрешил спор вариантами (a)+(b) вместе — четыре
литерала в `permissions.deny` референса (`docs/reference/role-home/
claude/settings.json`): `Bash(python3 orchestrator/artel.py init:*)`,
`Bash(python3 orchestrator/artel.py doctor --restore:*)`,
`Bash(openssl enc -d:*)`, `Bash(security find-generic-password:*)`.
Тест `test_ac13_...` ниже закрепляет наличие всех четырёх строк
буквально.

Красен до реализации:
- AC-13: `docs/reference/role-home/claude/settings.json` сегодня не
  существует вовсе (часть 1, 01M1NEEWH5K1XPFRDGRMPYSBXJ, которая
  заводит этот файл первыми четырьмя литералами требования 13, в этой
  рабочей копии не смержена — см. TZ.md/контекст SPEC) —
  `test_ac13_...` падает на `assertTrue(settings_path.exists())`.
- AC-14/AC-15: расшифровка пула (см. `test_pool_restore.py`) не
  существует — `test_ac14_...` падает на отсутствии incident-алерта
  (`alerts.open_alerts` пуст, расшифровывать нечему), `test_ac15_...`
  падает на отсутствии `[SystemExit]`/именованного отказа в выводе —
  без кода задачи `init` в фейковом role_env просто не находит
  `pool.sealed` и не расшифровывает НЕ ПОТОМУ, что распознал role_env,
  а потому, что восстановления ещё нет вовсе; это неверная краснота,
  но неотличимая от верной без первой половины задачи — то же
  ограничение честно указано в докстринге `test_pool_restore.py` для
  AC-7.

AC-14 и AC-15 тестируются НАПРЯМУЮ через `init` (тот же вход, что уже
доказанно триггерит расшифровку — AC-5), не через литералы CLI-вызова
из AC-13: наблюдаемое поведение («вызов аудирован», «в role_env —
отказ») не зависит от того, каким именно правилом `permissions.deny`
Bash-инструмент роли этот вызов блокирует снаружи — это ВТОРОЙ,
независимый рубеж (сам пульт отказывает, а не только курируемый слой
роли его не подпускает), обе половины требования 5 явно так и
разделены в SPEC.
"""
import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import alerts, config, store  # noqa: E402
from _sandbox import PoolBaseSandbox, REPO_ROOT  # noqa: E402

TEMPLATES = {"a.md": "тело А\n", "b.md": "тело Б\n"}


class PoolRestoreAuditTest(PoolBaseSandbox):

    def test_ac14_pool_decrypt_call_is_audited_with_an_incident_alert(self):
        """Легитимный вызов восстановления (Оператор, не роль): пул
        запечатан, каталог стёрт, `init` его расшифровывает — этот
        самый вызов обязан оставить запись аудита с алертом
        `kind=incident` (требование 5 SPEC: «аудит вызова … с алертом
        kind=incident», без условия на то, из чьего окружения вызов
        пришёл — это ВТОРАЯ половина требования, AC-15).

        Ловит мутацию: разработчик реализует расшифровку без аудита
        (или пишет его только в stdout, не через `alerts.raise_alert`,
        тем же классом дефекта, что описан для AC-15 части 1 канарейки
        v2, `tests/test_doctor_canary_pool.py`) — `open_alerts` после
        вызова останется пустым.
        """
        conn = store.db()
        store.create_schema(conn)
        baseline = len(alerts.open_alerts(conn, "incident"))

        self.write_pool_templates(TEMPLATES)
        self.seal()
        shutil.rmtree(self.pool_dir)

        self.restore_via_init()

        after = alerts.open_alerts(conn, "incident")
        self.assertGreater(
            len(after), baseline,
            f"вызов расшифровки пула (`init`, пул отсутствовал) не "
            f"поднял ни одного нового incident-алерта: {after}")


class RoleEnvRefusalTest(PoolBaseSandbox):
    """Отдельная песочница: `Path.home()`/`HOME`/`CLAUDE_CONFIG_DIR`
    ПЕРЕОПРЕДЕЛЕНЫ поверх базовых (после `super().setUp()`, `mock.patch`
    стекуется LIFO) на курируемый слой роли (`config.ROLE_HOME`/
    `config.ROLE_CONFIG_DIR`, `orchestrator/runner.py::role_env`,
    ЕДИНСТВЕННОЕ существующее в кодовой базе определение того, что такое
    «окружение роли») — именно так выглядело бы окружение процесса,
    запущенного `runner.role_env()` для настоящего шага роли.
    """

    def setUp(self):
        super().setUp()
        self.write_pool_templates(TEMPLATES)
        self.seal()
        shutil.rmtree(self.pool_dir)

        role_home_patcher = mock.patch.object(
            Path, "home", return_value=config.ROLE_HOME)
        role_home_patcher.start()
        self.addCleanup(role_home_patcher.stop)
        role_env_patcher = mock.patch.dict(
            "os.environ",
            {"HOME": str(config.ROLE_HOME),
             "CLAUDE_CONFIG_DIR": str(config.ROLE_CONFIG_DIR)})
        role_env_patcher.start()
        self.addCleanup(role_env_patcher.stop)
        self.role_pool_dir = config.ROLE_HOME / ".artel-canary"

    def test_ac15_pult_refuses_to_decrypt_pool_inside_role_environment(self):
        """`init`, вызванный из окружения, помеченного как роль
        (`HOME`/`CLAUDE_CONFIG_DIR` — курируемый слой роли), не
        расшифровывает пул НИКУДА — ни в `~/.artel-canary` этого
        окружения (которое для роли совпало бы с курируемым слоем,
        читаемым её же Bash/Read-инструментами), ни где-либо ещё — и
        называет причину отказа явно (именованный отказ, требование 5).

        Ловит мутацию: `init` в role_env падает по ДРУГОЙ причине
        (например, `OSError` курируемого слоя) без осмысленного
        сообщения — `assertIn` по ключевым словам причины ниже не
        находит ни одного из ожидаемых.
        """
        output = self.restore_via_init()

        self.assertFalse(
            self.role_pool_dir.exists(),
            f"`init` расшифровал пул внутри окружения роли "
            f"({self.role_pool_dir}) — требование 5 SPEC (AC-15) "
            f"нарушено: {output!r}")
        lowered = output.lower()
        self.assertTrue(
            any(kw in lowered for kw in ("role_env", "роль", "role")),
            f"отказ `init` в окружении роли не называет причину явно "
            f"(именованный отказ, требование 5): {output!r}")

    def test_ac15_control_outside_role_environment_restore_still_works(self):
        """Контроль к предыдущему тесту: та же расшифровка ВНЕ окружения
        роли (обычный `HOME`/`CLAUDE_CONFIG_DIR` Оператора) обязана
        по-прежнему срабатывать — отказ специфичен к role_env, не общая
        поломка восстановления.

        Ловит мутацию: разработчик реализует отказ слишком широко
        (например, всегда отказывает, если `CLAUDE_CONFIG_DIR` вообще
        задан в окружении, а не только когда он указывает на курируемый
        слой роли) — тогда пул не восстановился бы и здесь.
        """
        operator_home_patcher = mock.patch.object(
            Path, "home", return_value=self.fake_home)
        operator_home_patcher.start()
        self.addCleanup(operator_home_patcher.stop)
        operator_env_patcher = mock.patch.dict(
            "os.environ", {"HOME": str(self.fake_home), "CLAUDE_CONFIG_DIR": ""})
        operator_env_patcher.start()
        self.addCleanup(operator_env_patcher.stop)

        output = self.restore_via_init()
        self.assertTrue(
            self.pool_dir.exists(),
            f"восстановление отказало ВНЕ окружения роли — отказ AC-15 "
            f"должен быть специфичен к role_env: {output!r}")


class RoleDecryptionDenyRulesTest(unittest.TestCase):
    """Не песочница — проверяет СТАТИЧЕСКОЕ содержимое реального файла
    репозитория (`docs/reference/role-home/claude/settings.json`),
    буквально названного AC-13, без развёртывания/`init` (ту часть
    цепочки — «референс копируется в курируемый слой роли как есть» —
    уже проверяет часть 1 своим собственным тестом на СВОИ четыре
    литерала; см. докстринг модуля)."""

    def test_ac13_role_reference_denies_pool_decryption_and_restore_commands(self):
        """`permissions.deny` референса курируемого слоя роли несёт все
        четыре литерала, которыми ANSWER-1 п.2 закрыл требование 5:
        запрет ЦЕЛИКОМ на `init`/`doctor --restore` (вариант (a) —
        роли эти команды пульта не нужны в штатной работе) И запрет на
        прямой инструмент расшифровки в обход пульта, `openssl enc -d`/
        `security find-generic-password` (вариант (b)).

        Ловит мутацию: разработчик добавляет только часть из четырёх
        литералов (например, запрещает `init`/`doctor --restore`, но
        забывает про `openssl enc -d`/`security find-generic-password`,
        оставляя роли возможность расшифровать пул НАПРЯМУЮ в обход
        обеих команд, или наоборот) — соответствующий `assertIn` по
        недостающей строке падает, отличая «частично реализовано» от
        «реализовано полностью».
        """
        settings_path = (REPO_ROOT / "docs" / "reference" / "role-home" /
                         "claude" / "settings.json")
        self.assertTrue(
            settings_path.exists(),
            f"референс курируемого слоя роли не несёт settings.json: "
            f"{settings_path}")

        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self.fail(f"{settings_path} — невалидный JSON: {exc}")

        deny = (data.get("permissions") or {}).get("deny")
        self.assertIsInstance(
            deny, list,
            f"{settings_path}: нет списка permissions.deny "
            f"(документированный формат Claude Code) — {data}")
        combined = "\n".join(str(rule) for rule in deny)

        for needle in (
            "Bash(python3 orchestrator/artel.py init:*)",
            "Bash(python3 orchestrator/artel.py doctor --restore:*)",
            "Bash(openssl enc -d:*)",
            "Bash(security find-generic-password:*)",
        ):
            self.assertIn(
                needle, combined,
                f"permissions.deny референса не запрещает {needle!r} "
                f"(ANSWER-1 п.2, требование 5/AC-13): {deny}")


if __name__ == "__main__":
    unittest.main()
