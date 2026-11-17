import types, unittest
from inventory_batch import install
install()
from r2t.go import execution, mutation_copy

class InventoryBudgetTests(unittest.TestCase):
    def fake(self, remaining):
        obj=object.__new__(execution.ExecutionCopy)
        obj.quarantined=False
        obj._available=lambda:None
        obj._remaining=lambda argv:remaining
        obj.timeouts=[]
        def checked(*args, **kwargs):
            obj.timeouts.append(kwargs['timeout'])
            return 'R2T_INVENTORY/1\n\nR2T_INVENTORY_END\n'
        obj._checked=checked
        return obj

    def test_forward_deadline_preserved(self):
        for remaining in [5,30,100,600]:
            obj=self.fake(remaining)
            self.assertEqual(obj._inventory(forward=True),{})
            self.assertEqual(mutation_copy._inventory(obj,'/reference',forward=True),{})
            self.assertEqual(obj.timeouts,[min(180,remaining)]*2)

    def test_housekeeping_bound(self):
        obj=self.fake(1)
        obj._inventory()
        mutation_copy._inventory(obj,'/reference',forward=False)
        self.assertEqual(obj.timeouts,[180,180])

    def test_integrity_failure_still_quarantines(self):
        for reference in [False,True]:
            obj=self.fake(600)
            obj._checked=lambda *a,**kw:'truncated'
            with self.assertRaises(execution.ExecutionRefused):
                if reference:mutation_copy._inventory(obj,'/reference')
                else:obj._inventory()
            self.assertTrue(obj.quarantined)

if __name__=='__main__':unittest.main()
