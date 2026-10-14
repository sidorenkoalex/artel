"""Сохранение досыла: исполнение существующих проверок без копий ожиданий.

Группа: долгоживущий
Зелёный с рождения: существующие проверки однократности, возврата после ошибки БД, авторов, длины и общего лимита уже проходят.

unittest загружает именно существующие тесты, названные матрицей SPEC.
Это не новые копии сценариев: изменение поведения досыла обнаруживается
их исходными утверждениями. Песочницы и фикстуры принадлежат этим тестам.
"""
import io
import unittest


class DeliveryPreservedTest(unittest.TestCase):
    def run_existing(self, names):
        suite = unittest.defaultTestLoader.loadTestsFromNames(names)
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
        self.assertGreater(result.testsRun, 0, output.getvalue())
        self.assertFalse(result.skipped, output.getvalue())
        self.assertTrue(result.wasSuccessful(), output.getvalue())

    def test_ac6_delivery_once_retry_and_forbidden_action(self):
        """Исполняются прежние сценарии успешного и отказанного досыла.

        Ловит мутацию: файл остаётся после успеха, теряется при ошибке БД
        либо запрещённое действие доставляется — исходные проверки краснеют.
        """
        prefix = "tests.test_suite_run_deferred_journal.DeferredJournalTest."
        self.run_existing([prefix + name for name in (
            "test_delivered_once_with_role_session",
            "test_db_refusal_keeps_record_for_next_delivery",
            "test_forged_actor_and_foreign_action_are_not_delivered")])

    def test_ac7_authors_text_bound_and_shared_knowledge_limit(self):
        """Команда и очередь делят лимит; авторы и обрезка текста сохранены.

        Использованы исходные сценарии разных допустимых действий,
        смешанного потока и переполнения; лимиты берутся ими из config.
        Ловит мутацию: досыл меняет автора, перестаёт обрезать detail или
        считает отдельный лимит knowledge — прежние проверки краснеют.
        """
        self.run_existing([
            "tests.test_suite_run_deferred_journal.DeferredJournalTest."
            "test_forged_actor_and_foreign_action_are_not_delivered",
            "tests.test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_journal.DeliveryLimitTest",
            "tests.test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.DeferredJournalTest."
            "test_ac10_unwritable_db_defers_and_delivery_writes_once",
        ])
