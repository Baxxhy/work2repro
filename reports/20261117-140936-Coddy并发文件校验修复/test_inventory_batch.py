import pathlib, subprocess, tempfile, unittest
from inventory_batch import patch_support
SOURCE = pathlib.Path(__file__).with_name('original.sh').read_text()

def run(source, root):
    return subprocess.run(['bash','-c',source,'inventory-test','inventory',str(root)], capture_output=True)

class InventoryTests(unittest.TestCase):
    def test_exact_bytes_and_changed_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            for name in ['normal','with space','new\nline','tab\tname','-option','中文']:
                (root/name).write_bytes(b'\0binary\xff')
            before=run(SOURCE, root)
            after=run(patch_support(SOURCE), root)
            self.assertEqual(before.returncode,0)
            self.assertEqual(after.returncode,0)
            self.assertEqual(before.stdout,after.stdout)
            (root/'normal').write_text('changed')
            self.assertNotEqual(after.stdout,run(patch_support(SOURCE),root).stdout)
    def test_empty(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(run(SOURCE,root).stdout,run(patch_support(SOURCE),root).stdout)
    def test_nonregular_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            (root/'link').symlink_to('/etc/hostname')
            for source in (SOURCE,patch_support(SOURCE)):
                self.assertNotEqual(run(source,root).returncode,0)
    def test_large_inventory_and_fifo_refusal(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            for i in range(1100):
                (root/f'file-{i}').write_bytes(str(i).encode())
            old=run(SOURCE,root)
            new=run(patch_support(SOURCE),root)
            self.assertEqual((old.returncode,new.returncode),(0,0))
            self.assertEqual(old.stdout,new.stdout)
            os.mkfifo(root/'pipe')
            self.assertNotEqual(run(patch_support(SOURCE),root).returncode,0)

    def test_source_guard(self):
        with self.assertRaises(RuntimeError):patch_support('changed')
if __name__=='__main__':unittest.main()
