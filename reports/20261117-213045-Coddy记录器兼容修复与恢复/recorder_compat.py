"""Recorder correction: an unstarted step cannot emit a passed status.

All official witness readers, mutation labels and integrity checks stay intact.
The upstream parent-FailNow crash rule still decides the execution outcome.
"""
import sys

OLD = b'''func (f *r2tFormatter) Passed(p *messages.Pickle, s *messages.PickleStep, d *formatters.StepDefinition) {
\tf.BaseFmt.Passed(p, s, d)
'''
NEW = b'''func (f *r2tFormatter) Passed(p *messages.Pickle, s *messages.PickleStep, d *formatters.StepDefinition) {
\t// Godog can defer Passed with no definition when a Before hook calls
\t// FailNow/Goexit. No step ran: leave the crash prefix incomplete rather
\t// than inventing a passed step with time.Since(time.Time{}).
\tif _, started := f.starts[p.Id+"/"+s.Id]; !started && d == nil {
\t\treturn
\t}
\tf.BaseFmt.Passed(p, s, d)
'''

def corrected(source):
    if source.count(OLD) != 1:
        raise RuntimeError('Pinned Godog recorder differs from expected source')
    return source.replace(OLD, NEW, 1)

def install():
    from r2t.go import registry
    if getattr(registry.support_files, '_before_goexit_fix', False):
        return
    original = registry.support_files
    def support_files():
        files = original()
        key = '_bench/go/support/harness.go'
        files[key] = corrected(files[key])
        return files
    support_files._before_goexit_fix = True
    # Bind already-imported references to the same recorder source.
    for name, module in list(sys.modules.items()):
        if name.startswith("r2t.go") and getattr(module, "support_files", None) is original:
            module.support_files = support_files
    registry.support_files = support_files
