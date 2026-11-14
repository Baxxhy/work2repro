import json
import tempfile
import unittest
from pathlib import Path
from generation_outcome import inspect_req_generation


class ClassificationTest(unittest.TestCase):
    def classify(self, stop, calls, events, files=None, extra=''):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'workspaces').mkdir()
            (root / 'workspaces/0000.log').write_text(''.join(json.dumps(x)+'\n' for x in events))
            (root / 'job.log').write_text(f'[0] {stop} after {calls} LLM call(s), 0 file(s)\n' + extra)
            p = root / 'predictions.jsonl'
            if files is not None:
                p.write_text(json.dumps(dict(instance_id='task', files=files))+'\n')
            return inspect_req_generation(p, root, 'task')

    def test_network_empty_prediction_is_not_success(self):
        self.assertEqual(self.classify('timed out', 1, [{'type':'error','message':'Reconnecting... Connection failed'}], [])['kind'], 'infrastructure')

    def test_network_partial_file_is_not_success(self):
        self.assertEqual(self.classify('timed out', 10, [{'type':'error','message':'error sending request'}], [{'path':'t.py'}])['kind'], 'infrastructure')

    def test_zero_calls_timeout_is_infrastructure(self):
        self.assertEqual(self.classify('timed out', 0, [], [])['kind'], 'infrastructure')

    def test_normal_no_file_is_a_result(self):
        self.assertEqual(self.classify('exit 0', 12, [{'type':'turn.completed'}], [])['kind'], 'result')

    def test_normal_timeout_is_budget_result(self):
        self.assertEqual(self.classify('timed out', 45, [{'type':'item.completed'}], [])['reason'], 'official_wall_clock_budget')

    def test_call_budget_is_not_retried(self):
        self.assertEqual(self.classify('stopped at the budget', 200, [{'type':'error','message':'error sending request'}], [])['kind'], 'result')

    def test_recovered_transient_network_error_does_not_retry(self):
        self.assertEqual(self.classify('exit 0', 8, [{'type':'error','message':'Reconnecting'}, {'type':'turn.completed'}], [])['kind'], 'result')

    def test_pre_model_process_exhaustion(self):
        self.assertEqual(self.classify('exit 1', 0, [], extra='BlockingIOError: Resource temporarily unavailable')['kind'], 'infrastructure')

    def test_missing_prediction_after_terminal_is_infrastructure(self):
        self.assertEqual(self.classify('exit 0', 4, [{'type':'turn.completed'}])['kind'], 'infrastructure')


if __name__ == '__main__':
    unittest.main()
