import unittest
import tempfile

from cursibench.benchmark import run_benchmark, score
from cursibench.harness import run_harness
from cursibench.tasks import make_tasks
from cursibench.verifier import verify
from cursibench.service_pipeline import run_service_chain
from cursibench.protocol import BenchmarkSpec, validate_spec
from cursibench.agentrouter import MODEL_CHOICES


class BenchmarkTests(unittest.TestCase):
    def test_resettable_fixtures_are_independent(self):
        tasks = make_tasks()
        first = run_harness(tasks[0], "scoped")
        second = run_harness(tasks[0], "scoped")
        self.assertEqual(first.final_state, second.final_state)
        self.assertEqual(tasks[0].initial["slides"][0]["kpis"]["Q3"], 125)

    def test_verifier_catches_wrong_object_mutation(self):
        task = make_tasks()[0]
        state = run_harness(task, "naive").final_state
        score_value, errors = verify(task, state)
        self.assertLess(score_value, 1.0)
        self.assertTrue(errors)

    def test_rsi_loop_improves_hidden_split(self):
        result = run_benchmark(5)
        self.assertTrue(result["passed"])
        self.assertGreater(result["delta_rsi"], 0)
        self.assertEqual(result["final_policy"], "scoped")

    def test_service_chain_persists_auditable_result(self):
        with tempfile.TemporaryDirectory() as run_dir:
            result = run_service_chain(
                run_dir,
                [{"messages": [{"role": "user", "content": "edit slide"}]}],
            )
        self.assertEqual(result["chain"], [
            "data_generation_agent", "train_messages.jsonl", "tinker_lora_sft",
            "tinker_sampler_checkpoint", "e2b_tool_call_proxy", "harbor_benchmark_eval",
            "scored_attempt", "final_submission",
        ])
        self.assertEqual(result["provider_mode"], "local-fake")
        self.assertEqual(result["evaluation"]["harbor_errors"], [])
        self.assertFalse(result["final_submission"]["eligible"])
        self.assertIsNone(result["evaluation"]["score"])

    def test_protocol_freezes_verifier_and_hides_test(self):
        spec = BenchmarkSpec()
        validate_spec(spec)
        self.assertEqual(spec.repeats, 3)
        self.assertFalse(spec.test_visible_to_improver)
        self.assertIn("verifier", spec.frozen_surfaces)
        self.assertEqual(MODEL_CHOICES, ("gpt-6-astra", "gpt-5.6-sol"))


if __name__ == "__main__":
    unittest.main()
