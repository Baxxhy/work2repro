import re

from conftest import plain, text


def test_list_filters_by_project_glob_and_preserves_duplicates(invoke):
    src=('2024-01-01 08:00 - 2024-01-01 08:10 | Alpha | same\n'
         '2024-01-01 08:10 - 2024-01-01 08:20 | Alpine | same\n'
         '2024-01-02 08:00 - 2024-01-02 08:10 | alpha | other\n')
    p, _=invoke('list','--no_grouping','-p','Alp*',content=src)
    out=plain(p.stdout)
    assert p.returncode == 0 and out.count('same') == 2 and 'Alpha' in out and 'Alpine' in out and 'other' not in out


def test_list_date_range_limit_applied_after_filter(invoke):
    src=('2024-01-01 08:00 - 2024-01-01 08:10 | P | first\n'
         '2024-01-02 08:00 - 2024-01-02 08:10 | P | middle\n'
         '2024-01-03 08:00 - 2024-01-03 08:10 | P | final\n')
    p, _=invoke('list','--no_grouping','--from','2024-1-2','--to','2024-01-03','-n','1',content=src)
    out=plain(p.stdout)
    assert p.returncode == 0 and 'final' in out and 'middle' not in out and 'first' not in out


def test_list_date_and_no_results(invoke):
    p, _=invoke('list','--date','2024-01-02',content='2024-01-01 08:00 - 2024-01-01 08:10 | P | old\n')
    assert p.returncode == 0 and text(p.stdout) == 'No activity to display\n'


def test_list_and_report_reject_conflicting_date_filters(invoke):
    for cmd in ('list','report'):
        p, _=invoke(cmd,'--today','--yesterday',content='')
        assert p.returncode == 1 and b'cannot be used with' in p.stderr
        p, _=invoke(cmd,'--date','2024-01-01','--from','2024-01-01')
        assert p.returncode == 1 and p.stderr


def test_list_rounding_and_exact_duration_format(invoke):
    p, _=invoke('list','--no_grouping','--round','15m',content='2024-01-01 09:12 - 2024-01-01 10:23 | P | task\n')
    out=plain(p.stdout)
    assert p.returncode == 0 and '09:15' in out and '10:30' in out and '1h 15m' in out


def test_list_second_normalization_and_leap_second_duration(invoke):
    p, _=invoke('list','--no_grouping',content='2024-01-01 10:00:00 - 2024-01-01 10:00:60 | P | task\n')
    out=plain(p.stdout)
    assert p.returncode == 0 and out.count('10:00') >= 2 and '01m' in out


def test_report_aggregates_exact_project_description_and_total(invoke):
    src=('2024-01-01 08:00 - 2024-01-01 08:43 | P | Same\n'
         '2024-01-01 08:43 - 2024-01-01 09:25 | P | Same\n'
         '2024-01-01 08:00 - 2024-01-01 08:10 | p | Same\n')
    p, _=invoke('report',content=src)
    out=plain(p.stdout)
    assert p.returncode == 0 and 'P' in out and 'p' in out and out.count('Same') == 2 and 'Total' in out and '1h 25m' in out


def test_empty_report_has_total(invoke):
    p, _=invoke('report',content='')
    assert p.returncode == 0 and 'Total' in plain(p.stdout) and '<1m' in plain(p.stdout)


def test_projects_unique_case_sensitive_sorted_quotes_and_current(invoke):
    src=('2024-01-01 08:00 - 2024-01-01 09:00 | projecta | a\n'
         '2024-01-01 09:00 | ProjectA | b\n'
         '2024-01-01 10:00 | "ProjectA" | c\n')
    p, _=invoke('projects',content=src)
    assert p.returncode == 0 and text(p.stdout).splitlines() == ['""ProjectA""','"PROJECTA"','"ProjectA"','"projecta"']
    p, _=invoke('projects','--no-quotes','--current')
    assert text(p.stdout).splitlines() == ['"ProjectA"','ProjectA']


def test_last_and_continue_use_chronological_distinct_history(invoke):
    src=('2024-01-03 09:00 - 2024-01-03 09:05 | P3 | C\n'
         '2024-01-01 09:00 - 2024-01-01 09:05 | P1 | A\n'
         '2024-01-02 09:00 - 2024-01-02 09:05 | P2 | B\n'
         '2024-01-04 09:00 - 2024-01-04 09:05 | P3 | C\n')
    p, _=invoke('last',content=src)
    out=plain(p.stdout)
    assert p.returncode == 0 and out.index('[2]') < out.index('[1]') < out.index('[0]')
    p, log=invoke('continue','1','-t','10:00',content=src)
    assert p.returncode == 0 and 'Started activity: "B" (P2)' in text(p.stdout)
    assert log.read_text().endswith('10:00 | P2 | B\n')


def test_last_zero_and_continue_bounds(invoke):
    p, _=invoke('last','-n','0',content='2024-01-01 09:00 - 2024-01-01 09:01 | P | A\n')
    assert p.returncode == 0 and text(p.stdout) == 'No activities have been tracked yet\n'
    p, log=invoke('continue','1','-t','10:00',content='2024-01-01 09:00 - 2024-01-01 09:01 | P | A\n')
    assert p.returncode == 0 and log.read_text().endswith('10:00 | P | A\n')
    p, _=invoke('continue','2',content='2024-01-01 09:00 - 2024-01-01 09:01 | P | A\n')
    assert p.returncode == 1 and b'Less than 2 distinct' in p.stderr


def test_search_case_insensitive_glob_and_missing_term(invoke):
    src=('2024-01-01 09:00 - 2024-01-01 09:01 | Project | Hello World\n'
         '2024-01-02 09:00 - 2024-01-02 09:01 | Other | second\n')
    p, _=invoke('search','hello*',content=src)
    assert p.returncode == 0 and 'Hello World' in plain(p.stdout) and 'second' not in plain(p.stdout)
    p, _=invoke('search',content=src)
    assert p.returncode == 0 and text(p.stdout) == 'No matching activities found'
    p, _=invoke('search','',content=src)
    assert p.returncode == 0 and 'Hello World' in plain(p.stdout) and 'second' in plain(p.stdout)


def test_current_selects_running_in_file_order(invoke):
    p, _=invoke('current',content='2024-01-01 09:00 - 2024-01-01 10:00 | P | closed\n2024-01-01 11:00 | Q | second\n2024-01-01 10:00 | P | first\n')
    out=plain(p.stdout)
    assert p.returncode == 0 and 'closed' not in out and out.index('second') < out.index('first')


def test_current_empty_message(invoke):
    p, _=invoke('current',content='')
    assert p.returncode == 0 and text(p.stdout) == 'No Activity is currently running'


def test_sanity_negative_duration_and_overlaps(invoke):
    src=('2024-01-01 09:00 - 2024-01-01 10:00 | P | first\n'
         '2024-01-01 09:30 - 2024-01-01 11:00 | P | overlap\n'
         '2024-01-01 12:00 - 2024-01-01 11:00 | P | negative\n')
    p, _=invoke('sanity',content=src)
    out=text(p.stdout)
    assert p.returncode == 0 and 'Activity started before another activity ended' in out and 'Activity has negative duration' in out
    assert out.index('overlap') < out.index('negative')


def test_sanity_clean(invoke):
    p, _=invoke('sanity',content='2024-01-01 09:00 - 2024-01-01 10:00 | P | A\n')
    assert p.returncode == 0 and text(p.stdout) == 'No unusual activities.\n'


def test_status_empty_layout_and_project_filter(invoke):
    p, _=invoke('status',content='')
    out=plain(p.stdout)
    assert p.returncode == 0 and 'Status for ALL projects' in out and 'NO Activity' in out
    p, _=invoke('status','-p','NoSuchProject')
    assert p.returncode == 0 and 'Status for project: NoSuchProject' in plain(p.stdout)


def test_status_project_filter_applies_to_running_and_totals(invoke):
    p, _=invoke('status','-p','P',content='2024-01-01 09:00 - 2024-01-01 09:10 | Q | completed\n')
    assert p.returncode == 0 and 'Status for project: P' in plain(p.stdout)
    assert 'NO Activity' in plain(p.stdout)


def test_edit_executes_editor_with_log_path_argument(invoke, tmp_path):
    p, log=invoke('edit','-e','cat',content='2024-01-01 09:00 | P | D\n',env={'EDITOR':'unused'})
    assert p.returncode == 0 and p.stdout == log.read_bytes()


def test_edit_missing_editor_and_explicit_empty(invoke):
    p, _=invoke('edit',env={'EDITOR':None})
    assert p.returncode == 1 and b'editor command is missing' in p.stderr
    p, _=invoke('edit','-e','',content='')
    assert p.returncode == 1 and b'No such file or directory' in p.stderr
