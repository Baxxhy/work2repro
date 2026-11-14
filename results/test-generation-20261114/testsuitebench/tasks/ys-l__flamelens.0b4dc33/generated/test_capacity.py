from test_tui import tui


def test_counts_and_aggregates_exceed_32_bit_range():
    rc, screen, _ = tui('big 9000000000\nother 9000000000\n', keys=b'\tq')
    assert rc == 0
    assert '18000000000' in screen
    assert '9000000000' in screen


def test_thousand_siblings_render_in_top_view():
    folded = ''.join(f'root;frame{i:04d} 1\n' for i in range(1000))
    rc, screen, _ = tui(folded, keys=b'\tq', width=120, height=40, timeout=5)
    assert rc == 0 and 'frame0000' in screen and 'frame0999' in screen


def test_two_hundred_fifty_level_stack_can_be_searched_and_navigated():
    stack = ';'.join(f'level{i}' for i in range(250))
    rc, screen, _ = tui(stack + ' 1\n', keys=b'/level249\nq', height=30, timeout=5)
    assert rc == 0 and 'level249' in screen


def test_ten_thousand_unique_stacks_parse_and_render_promptly():
    folded = ''.join(f'root;branch{i:05d} 1\n' for i in range(10000))
    rc, screen, _ = tui(folded, keys=b'\tq', width=120, height=40, timeout=5)
    assert rc == 0 and 'branch00000' in screen and 'branch09999' in screen


def test_ten_thousand_line_echo_is_complete():
    folded = ''.join(f'frame{i} 1\n' for i in range(10000))
    rc, _, out = tui(folded, keys=b'q', args=('--echo',), timeout=5)
    assert rc == 0 and out == (folded + '\n').encode()
