import unittest
from pathlib import Path

from agenteval.benchmark import load_benchmark

ROOT = Path(__file__).resolve().parents[1]


class BenchmarkTests(unittest.TestCase):
    def test_customer_risk_benchmark_loads(self):
        benchmark = load_benchmark(ROOT / "benchmarks" / "customer_risk.yaml")
        self.assertEqual(benchmark["suite_id"], "customer_risk_v1")
        self.assertEqual(len(benchmark["tasks"]), 15)


if __name__ == "__main__":
    unittest.main()
