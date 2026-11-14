import os
from pathlib import Path


def test_missing_config_directories_are_nonfatal_with_warning(invoke, tmp_path):
    nowhere = tmp_path / "does-not-exist"
    r = invoke("-n", "1", env={"HTOPRC": "", "XDG_CONFIG_HOME": str(nowhere / "xdg"), "HOME": str(nowhere / "home")})
    assert r.returncode == 0 and r.stdout
    assert r.stderr == b"Cannot save configuration to : No such file or directory\n"


def test_unwritable_explicit_config_falls_back(invoke):
    r = invoke("-n", "1", env={"HTOPRC": "/proc/htop-eval-no-such-dir/htoprc"})
    assert r.returncode == 0 and r.stdout
    assert r.stderr == b"Cannot save configuration to /proc/htop-eval-no-such-dir/htoprc: No such file or directory\n"


def test_config_file_creation_reuse_and_empty_file(invoke, tmp_path):
    cfg = tmp_path / "htoprc"
    r = invoke("-n", "1", env={"HTOPRC": cfg})
    assert r.returncode == 0 and r.stdout and cfg.exists() and cfg.read_text()
    original = cfg.read_text()
    assert invoke("-n", "1", env={"HTOPRC": cfg}).returncode == 0
    assert cfg.read_text() == original
    empty = tmp_path / "emptyrc"
    empty.write_text("")
    r = invoke("-n", "1", env={"HTOPRC": empty})
    assert r.returncode == 0 and r.stdout


def test_invalid_config_entries_are_tolerated(invoke, tmp_path, plain):
    cfg = tmp_path / "badrc"
    cfg.write_text("unknown_key=blah\nnot a valid line\nfields=\n")
    r = invoke("-n", "1", env={"HTOPRC": cfg})
    assert r.returncode == 0 and r.stderr == b"" and "PID" in plain(r.stdout)


def test_invalid_only_fields_keep_meters_without_process_table(invoke, tmp_path, plain):
    cfg = tmp_path / "invalid-fields"
    cfg.write_text("fields=NOT_A_REAL_FIELD ALSO_BAD\n")
    r = invoke("-n", "1", env={"HTOPRC": cfg})
    visible = plain(r.stdout)
    assert r.returncode == 0 and r.stderr == b""
    assert "CPU" in visible and "PID" not in visible


def test_config_fields_and_legacy_columns_are_accepted(invoke, tmp_path, plain):
    for value, expected in (("PID USER RCHAR", "PID"), ("0 48 17 18 38 39 2 46 47 49 1", None), ("Command", "Command")):
        cfg = tmp_path / ("fields-" + str(len(value)))
        cfg.write_text("fields=" + value + "\n")
        r = invoke("-n", "1", env={"HTOPRC": cfg})
        assert r.returncode == 0 and r.stdout
        if expected:
            assert expected.lower() in plain(r.stdout).lower()


def test_all_documented_field_names_are_valid_in_config(invoke, tmp_path):
    from test_views import FIELDS
    cfg = tmp_path / "all-fields"
    cfg.write_text("fields=" + " ".join(FIELDS) + "\n")
    r = invoke("-n", "1", env={"HTOPRC": cfg})
    assert r.returncode == 0 and r.stdout


def test_config_sort_tree_directions_and_screen_blocks(invoke, tmp_path):
    cfg = tmp_path / "screenrc"
    cfg.write_text("sort_key=PID\nsort_direction=-1\ntree_view=1\ntree_sort_direction=1\nall_branches_collapsed=0\nscreen:Main=PID USER Command\n.sort_key=USER\n.sort_direction=1\n")
    r = invoke("-n", "1", env={"HTOPRC": cfg})
    assert r.returncode == 0 and r.stdout


def test_boolean_config_preferences_and_cli_override(invoke, tmp_path):
    cfg = tmp_path / "preferences"
    keys = "delay hide_kernel_threads hide_userland_threads shadow_other_users show_thread_names show_program_path highlight_base_name highlight_deleted_exe highlight_megabytes highlight_threads find_comm_in_cmdline strip_exe_from_cmdline show_merged_command detailed_cpu_time cpu_count_from_one show_cpu_usage show_cpu_frequency show_cpu_temperature update_process_names account_guest_in_cpu_meter header_margin highlight_changes highlight_changes_delay_secs tree_view_always_by_pid all_branches_collapsed shadow_distribution_path_prefix".split()
    cfg.write_text("".join(key + "=1\n" for key in keys))
    r = invoke("-n", "8", "-d", "1", "--no-meters", env={"HTOPRC": cfg})
    assert r.returncode == 0 and r.stdout and len(r.stdout) > 1000


def test_meter_configuration_modes_and_no_meters_override(invoke, tmp_path, plain):
    cfg = tmp_path / "meters"
    cfg.write_text("column_meters_0=CPU Memory Tasks\ncolumn_meter_modes_0=1 2 4\ncolumn_meters_1=Swap LoadAverage Uptime DiskIO NetworkIO FileDescriptors Battery Clock DateTime Hostname SysArch Systemd\ncolumn_meter_modes_1=2 3 1 4 1 2 3 4 1 2 3 4\n")
    r = invoke("-n", "1", env={"HTOPRC": cfg})
    assert r.returncode == 0 and "PID" in plain(r.stdout)
    no_meters = invoke("-n", "1", "--no-meters", env={"HTOPRC": cfg})
    assert no_meters.returncode == 0 and "PID" in plain(no_meters.stdout)
