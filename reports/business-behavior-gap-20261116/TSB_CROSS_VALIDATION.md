# TestSuiteBench交叉核验


## 样本与计分边界

从已发布165条结果中固定6个任务。低分组为zoxide、pueue、rnr、duckdb，均Validity≥0.8且Mutation Score≤0.25，进一步按状态或业务流程需求定向选择。doxygen为高Validity、高Mutation Score对照，eureka为相对较高Mutation Score且有明确Git状态流程的补充对照。不同应用的规格长度、变异池和任务难度没有匹配，不能据此比较因果效应或估计165条中的发生率。

Validity按正确实现上的测试实例通过数/测试实例数核对。Mutation Score按至少被一个正确实现通过的测试实例杀死的变异数/有效变异数核对。参数化实例按官方test_results名称计数。下列6个套件都有部分测试在正确实现失败，故高Validity不能写成整个套件通过。

每个任务抽取官方结果顺序中的前三个存活变异和首个被杀死控制，共24个，保存元数据与源码diff。选择顺序与元数据文件顺序可能不同，以下结果逐个按binary_id核验。源文件从已有reference_impl归档匹配，新增文件在reference-source-audit.json记录。共享条件分支源码按assignment_id/编译选择解释，不能把整份diff的所有分支当成一个变异。


[固定清单](selection.json)

|任务|正确实现通过/总数|Validity|杀死/变异数|Mutation Score|
|---|---|---|---|---|
|ajeetdsouza__zoxide.67ca1bc|18/19|0.9474|8/39|0.2051|
|nukesor__pueue.8b9d6fe|45/48|0.9375|10/61|0.1639|
|ismaelgv__rnr.fc0733b|42/45|0.9333|11/72|0.1528|
|duckdb__duckdb.bdb65ec|72/84|0.8571|6/39|0.1538|
|doxygen__doxygen.966d98e|30/31|0.9677|30/41|0.7317|
|simeg__eureka.df3796c|25/27|0.9259|22/54|0.4074|


## ajeetdsouza__zoxide.67ca1bc

### 局部输入缺失与有效业务操作并存


add/query/remove/import/edit实际操作与状态检查均存在。repo_1接受重复--score、repo_3接受空路径、repo_4隐藏help中的score，均存活。repo_2非数字score变异被test_usage_errors_are_status_two[bad-score]杀死。不能把四条选中元数据都标为存活。当前材料支持局部输入或帮助契约覆盖差异，未确认业务操作整体被替代。

[完整原始规格](cases/01/requirements/spec.md)；[官方逐测试执行记录](cases/01/official-test-eval.json)；[原有结果矩阵](cases/01/failure-matrix.csv)

[test_cli.py](cases/01/generated/eval/test_cli.py) 第31—58行

```text
  31 
  32 def add_dir(ctx, name, *args):
  33     _, cwd, _, call = ctx
  34     p = cwd / name
  35     p.mkdir(parents=True, exist_ok=True)
  36     r = call("add", *args, str(p))
  37     assert r.returncode == 0, r.stderr
  38     assert r.stdout == b"" and r.stderr == b""
  39     return str(p)
  40 
  41 
  42 def test_root_version_help_and_bare_invocation(ctx):
  43     *_, call = ctx
  44     assert call("--version").stdout == b"zoxide 0.9.9\n"
  45     h = call("--help")
  46     bare = call()
  47     assert h.returncode == 0 and h.stdout.startswith(b"zoxide 0.9.9\n")
  48     assert bare.returncode == 2 and bare.stderr == h.stdout
  49 
  50 
  51 @pytest.mark.parametrize("args", [("add",), ("init",), ("import",), ("add", "--score", "x", "/tmp")], ids=["add-required", "init-required", "import-required", "bad-score"])
  52 def test_usage_errors_are_status_two(ctx, args):
  53     *_, call = ctx
  54     r = call(*args)
  55     assert r.returncode == 2 and not r.stdout and r.stderr.startswith(b"error:")
  56 
  57 
  58 def test_add_normalizes_accumulates_and_query_formats_scores(ctx):
```

### 被引用测试的实际状态


|测试实例|正确实现状态|
|---|---|
|test_cli.test_usage_errors_are_status_two[bad-score]|passed|


### 选中变异的执行结果


|binary_id / assignment_id|具体修改|有效测试杀死|杀死测试|证据|
|---|---|---|---|---|
|repo_1 / repo_2|Enables scalar argument self-overrides for `add`, so repeated `--score` options are accepted and the last value wins instead of producing a usage error.|否|无|[源码差分](cases/01/repo_1.patch)|
|repo_2 / repo_4|Defers score parsing and falls back to 1.0 on parse failure, so nonnumeric `--score` text is accepted.|是|test_cli.test_usage_errors_are_status_two[bad-score]|[源码差分](cases/01/repo_2.patch)|
|repo_3 / repo_3|Parses add paths as unrestricted strings, allowing the empty positional value to resolve to the current directory instead of being rejected by the CLI.|否|无|[源码差分](cases/01/repo_3.patch)|
|repo_4 / repo_7|Hides `--score` from add help while leaving the option functional, making the documented add interface incomplete.|否|无|[源码差分](cases/01/repo_4.patch)|


正确实现失败的测试实例包括 test_cli.test_all_controls_unavailable_pruning_and_list_empty_success。


## nukesor__pueue.8b9d6fe

### A工作流覆盖缺失与C帮助内容断言不足


规格明确要求与提供的daemon通信，并要求组隔离、依赖与持久任务状态。全部48个测试实例集中于help/version、解析、配置错误及缺失socket。没有成功提交并观察任务状态的流程。该套件业务覆盖缺失已确认，但不能仅凭现有报告判定生成时是否具备可用daemon。

单独可与存活直接对照的C证据是test_each_command_has_standalone_help只检查退出0、非空stdout和空stderr。repo_4把enqueue描述改为queued，repo_5把env改成只读，repo_6把follow改成快照，全部存活；明确帮助语义不受该断言约束。这些CLI文字证据与业务状态缺失分开记载，尚未建立工作流缺失对具体状态变异的漏检因果。

[完整原始规格](cases/02/requirements/spec.md)；[官方逐测试执行记录](cases/02/official-test-eval.json)；[原有结果矩阵](cases/02/failure-matrix.csv)

[spec.md](cases/02/requirements/spec.md) 第39—65行

```text
  39 add          Enqueue a task for execution
  40 remove       Remove tasks from the list. Running or paused tasks need to be killed first
  41 switch       Switches the queue position of two commands
  42 stash        Stash a task. Stashed tasks won't be automatically started
  43 enqueue      Enqueue stashed tasks. They'll be handled normally afterwards
  44 start        Resume operation of specific tasks or groups of tasks
  45 restart      Restart failed or successful task(s)
  46 pause        Either pause running tasks or specific groups of tasks
  47 kill         Kill specific running tasks or whole task groups
  48 send         Send something to a task. Useful for sending confirmations such as 'y\n'
  49 edit         Adjust editable properties of a task
  50 env          Use this to add or remove environment variables from tasks
  51 group        Use this to add or remove groups
  52 status       Display the current status of all tasks
  53 log          Display the log output of finished tasks
  54 follow       Follow the output of a currently running task. This command works like "tail -f"
  55 wait         Wait until tasks are finished
  56 clean        Remove all finished tasks from the list
  57 reset        Kill all tasks, clean up afterwards and reset EVERYTHING!
  58 shutdown     Remotely shut down the daemon. Should only be used if the daemon isn't started by a service manager
  59 parallel     Set the amount of allowed parallel tasks
  60 completions  Generates shell completion files
  61 help         Print this message or the help of the given subcommand(s)
  62 ```
  63 
  64 Long help starts with `Interact with the Pueue daemon`, then `Use the \`--help\` long form to get detailed help output on each subcommand!`, a blank line, usage, the command list, and the global options. `-h` uses the same content but compact option layout; `--help` uses multiline descriptions. Output wraps according to the `COLUMNS` environment variable (notably at 80 columns). Every command accepts `-h/--help`, exits 0, and describes exactly the arguments/options and behavior assigned to it in this document. Unknown commands/options and missing arguments use conventional lowercase Clap-style diagnostics, including a `Usage:` line and `For more information, try '--help'.` For example:
  65 
```

[spec.md](cases/02/requirements/spec.md) 第458—466行

```text
 458 ## Spec 24
 459 
 460 The following integration invariants must hold across commands because they are directly observable through the supplied daemon:
 461 
 462 - Commands and all task metadata survive client invocations exactly; IDs and environments are never confused during rapid additions/status queries.
 463 - Groups are independent queues. Pausing, starting, killing, setting parallelism, or selecting one group must not affect another. Parallel value zero means unlimited.
 464 - Same-priority queued work is FIFO. Higher numeric priority is chosen before lower priority once a slot is free. Explicit dependencies block execution until every dependency succeeds; any failed dependency produces Done/DependencyFailed. Dependency lists are sorted and deduplicated by the daemon and visible in state.
 465 - `--immediate` and explicit `start ID` force a task despite group pause, parallel limits, and dependencies. A normal task added to a paused group stays Queued and produces the warning in Spec 6.
 466 - Captured environments and later `env` edits are used by the task process; working directories are honored; shell operators and quoting execute according to the daemon-provided shell.
```

[test_cli.py](cases/02/generated/eval/test_cli.py) 第59—69行

```text
  59 @pytest.mark.parametrize("command", ["add", "remove", "switch", "stash", "enqueue", "start", "restart",
  60                                       "pause", "kill", "send", "edit", "env", "group", "status", "log",
  61                                       "follow", "wait", "clean", "reset", "shutdown", "parallel", "completions"],
  62                          ids=["add", "remove", "switch", "stash", "enqueue", "start", "restart", "pause",
  63                               "kill", "send", "edit", "env", "group", "status", "log", "follow", "wait",
  64                               "clean", "reset", "shutdown", "parallel", "completions"])
  65 def test_each_command_has_standalone_help(command):
  66     result = invoke(command, "--help")
  67     assert result.returncode == 0
  68     assert result.stdout
  69     assert result.stderr == b""
```

[test_cli.py](cases/02/generated/eval/test_cli.py) 第232—244行

```text
 232 def test_absent_socket_report_preserves_nested_causes(tmp_path):
 233     sock = str(tmp_path / "missing.sock")
 234     secret = tmp_path / "secret"
 235     secret.write_bytes(b"secret")
 236     config = write_config(tmp_path, f"shared:\n  unix_socket_path: {sock}\n  shared_secret_path: {secret}\n")
 237     result = invoke("-c", config, "status")
 238     err = result.stderr.decode(errors="replace")
 239     assert result.returncode != 0
 240     assert "Failed to initialize client." in err
 241     assert "Failed to initialize stream." in err
 242     assert f'I/O error at path "{sock}"' in err
 243     assert "while connecting to daemon" in err
 244     assert "No such file or directory" in err
```

### 被引用测试的实际状态


|测试实例|正确实现状态|
|---|---|
|test_cli.test_each_command_has_standalone_help[enqueue]|passed|
|test_cli.test_each_command_has_standalone_help[env]|passed|
|test_cli.test_each_command_has_standalone_help[follow]|passed|


### 选中变异的执行结果


|binary_id / assignment_id|具体修改|有效测试杀死|杀死测试|证据|
|---|---|---|---|---|
|repo_1 / repo_1|The long version flag reports 4.0.5 instead of the required 4.0.4.|是|test_cli.test_version_forms_and_global_verbose_flags|[源码差分](cases/02/repo_1.patch)|
|repo_4 / repo_10|The enqueue help incorrectly says queued rather than stashed tasks are selected.|否|无|[源码差分](cases/02/repo_4.patch)|
|repo_5 / repo_11|The env help incorrectly describes a view-only operation.|否|无|[源码差分](cases/02/repo_5.patch)|
|repo_6 / repo_12|The follow help describes a snapshot instead of continuous following.|否|无|[源码差分](cases/02/repo_6.patch)|


正确实现失败的测试实例包括 test_cli.test_group_and_all_selection_conflict_is_parser_error、test_cli.test_add_option_conflicts_are_reported_before_connecting、test_cli.test_help_and_completions_do_not_require_configuration_or_daemon。


## ismaelgv__rnr.fc0733b

### C诊断内容约束不足，真实重命名流程存在


缺少命令/未知命令测试只检查部分前缀、退出码和unrecognized文本。repo_1/2/3分别删除命令列表、usage或help提示后仍存活。该局部CLI预言不足不能扩展成未执行重命名。候选还有真实文件重命名、backup、dump/replay及undo检查，repo_25由regex_captures_and_transform杀死。global_help_and_version在正确实现失败，不能把它的失败用作有效杀死证据。

[完整原始规格](cases/03/requirements/spec.md)；[官方逐测试执行记录](cases/03/official-test-eval.json)；[原有结果矩阵](cases/03/failure-matrix.csv)

[test_cli.py](cases/03/generated/eval/test_cli.py) 第55—61行

```text
  55 def test_missing_and_unknown_commands(work):
  56     p = run([], work)
  57     assert p.returncode == 2 and p.stdout == '' and p.stderr.startswith('RnR is a command-line tool')
  58     p = run(['bogus'], work)
  59     assert p.returncode == 2 and "unrecognized subcommand 'bogus'" in p.stderr
  60     assert run(['help', '--help'], work).returncode == 2
  61 
```

[test_cli.py](cases/03/generated/eval/test_cli.py) 第163—188行

```text
 163 def test_chain_order_execution(work):
 164     for n in ('a.txt', 'aa.txt', 'aaa.txt'):
 165         (work / n).write_text(n)
 166     p = run(['regex', '-f', '--no-dump', 'a', 'aa', 'a.txt', 'aa.txt', 'aaa.txt'], work)
 167     assert p.returncode == 0
 168     lines = p.stdout.splitlines()
 169     assert lines == ['aaa.txt -> aaaa.txt', 'aa.txt -> aaa.txt', 'a.txt -> aa.txt']
 170     assert (work / 'aa.txt').read_text() == 'a.txt'
 171     assert (work / 'aaa.txt').read_text() == 'aa.txt'
 172     assert (work / 'aaaa.txt').read_text() == 'aaa.txt'
 173 
 174 
 175 def test_from_file_preview_force_undo_and_validation(work):
 176     dump = work / 'ops.json'
 177     write_dump(dump, [{'source': 'one', 'target': 'two'}, {'source': 'three', 'target': 'four'}])
 178     p = run(['from-file', str(dump)], work)
 179     assert p.returncode == 0 and p.stdout == 'This is a DRY-RUN\none -> two\nthree -> four\n'
 180     (work / 'two').write_text('2'); (work / 'four').write_text('4')
 181     q = run(['from-file', '-f', '--no-dump', '-u', str(dump)], work)
 182     assert q.returncode == 0 and (work / 'one').read_text() == '2' and (work / 'three').read_text() == '4'
 183     for content in ('', '{bad', '{"date":1,"operations":[]}','{"date":"x","operations":[{}]}'):
 184         bad = work / 'bad.json'; bad.write_text(content)
 185         r = run(['from-file', str(bad)], work)
 186         assert r.returncode == 1 and r.stdout == 'This is a DRY-RUN\n' and 'Cannot parse JSON file' in r.stderr
 187 
 188 
```

### 被引用测试的实际状态


|测试实例|正确实现状态|
|---|---|
|test_cli.test_missing_and_unknown_commands|passed|
|test_cli.test_chain_order_execution|passed|
|test_cli.test_from_file_preview_force_undo_and_validation|passed|


### 选中变异的执行结果


|binary_id / assignment_id|具体修改|有效测试杀死|杀死测试|证据|
|---|---|---|---|---|
|repo_1 / repo_1|[MUTATED] Violates Spec 1 by changing executable dispatch and path resolution in the compile-time-selected source branch for repo_1. The branch intentionally makes this assigned behavior false: Invoking the executable without a command fails and lists the regex, from-file, and to-ascii commands.|否|无|[源码差分](cases/03/repo_1.patch)|
|repo_2 / repo_2|[MUTATED] Violates Spec 1 by changing executable dispatch and path resolution in the compile-time-selected source branch for repo_2. The branch intentionally makes this assigned behavior false: Invoking the executable without a command fails and displays usage and command information.|否|无|[源码差分](cases/03/repo_2.patch)|
|repo_3 / repo_4|[MUTATED] Violates Spec 1 by changing executable dispatch and path resolution in the compile-time-selected source branch for repo_4. The branch intentionally makes this assigned behavior false: An unrecognized command fails and its diagnostic suggests using --help.|否|无|[源码差分](cases/03/repo_3.patch)|
|repo_25 / repo_53|[MUTATED] Violates Spec 9 by changing regular-expression compilation and matching in the compile-time-selected source branch for repo_53. The branch intentionally makes this assigned behavior false: The test verifies empty pattern matches start.|是|test_cli.test_regex_captures_and_transform|[源码差分](cases/03/repo_25.patch)|


正确实现失败的测试实例包括 test_cli.test_global_help_and_version、test_cli.test_cli_errors[hidden-needs-recursive]、test_cli.test_recursive_hidden_depth_and_dirs。


## duckdb__duckdb.bdb65ec

### 未确认同类业务缺口，存在参考实现失败测试


执行了实际SQL、文件持久化和重开。事务rollback测试在正确实现失败，不能作为成功验证事务的证据。前三个存活都涉及版本输出，而生成的version_contract、version_alias_and_sql_version、dot_version_first_two_lines在正确实现已失败，按有效测试口径无法贡献kill。这组证据主要体现无效测试与局部契约差异，不能据此确认B/C业务状态缺口。repo_7忽略--readonly写保护，被test_files_and_storage.test_readonly_alias_has_same_write_behavior杀死，支持真实存储边界得到检查。

[完整原始规格](cases/04/requirements/spec.md)；[官方逐测试执行记录](cases/04/official-test-eval.json)；[原有结果矩阵](cases/04/failure-matrix.csv)

[test_cli.py](cases/04/generated/eval/test_cli.py) 第4—17行

```text
   4 def test_version_contract(run):
   5     r = run("--version")
   6     ok(r)
   7     assert r.stdout == "v0.0.1 (Unknown Version) 780a7396\n"
   8     assert r.stderr == ""
   9 
  10 
  11 def test_version_alias_and_sql_version(run):
  12     r = run("-version")
  13     ok(r)
  14     assert r.stdout.splitlines() == ["v0.0.1 (Unknown Version) 780a7396"]
  15     r = run("-csv", "-c", "select version()")
  16     ok(r)
  17     assert r.stdout.strip() == "version()\nv0.0.1"
```

[test_cli.py](cases/04/generated/eval/test_cli.py) 第157—176行

```text
 157 def test_persistent_database_reopens_and_isolates(run, tmp_path):
 158     first = tmp_path / "one.duckdb"
 159     second = tmp_path / "two.duckdb"
 160     ok(run(first, "create table t(i int)", "insert into t values (9)"))
 161     r = run("-csv", first, "select sum(i) from t")
 162     ok(r)
 163     assert r.stdout.endswith("9\n")
 164     r = run("-csv", second, "show tables")
 165     ok(r)
 166     assert "t" not in r.stdout
 167 
 168 
 169 def test_readonly_reads_and_rejects_writes(run, tmp_path):
 170     db = tmp_path / "ro.duckdb"
 171     ok(run(db, "create table t(i int)", "insert into t values (3)"))
 172     r = run("--readonly", "-csv", db, "select * from t")
 173     ok(r)
 174     assert "3" in r.stdout
 175     r = run("-readonly", db, "insert into t values (4)")
 176     assert r.returncode != 0 and "read-only" in r.stderr.lower()
```

### 被引用测试的实际状态


|测试实例|正确实现状态|
|---|---|
|test_cli.test_persistent_database_reopens_and_isolates|passed|
|test_files_and_storage.test_readonly_alias_has_same_write_behavior|passed|


### 选中变异的执行结果


|binary_id / assignment_id|具体修改|有效测试杀死|杀死测试|证据|
|---|---|---|---|---|
|repo_1 / repo_3|Violates Spec 1 by placing a metadata-only line before the version-bearing -version line, so the first line has no source version.|否|无|[源码差分](cases/04/repo_1.patch)|
|repo_2 / repo_5|Violates Spec 1 by omitting the DuckDB product identifier from .version while retaining version and build fields.|否|无|[源码差分](cases/04/repo_2.patch)|
|repo_3 / repo_1|Violates Spec 1 by making the long --version spelling report v0.0.2 instead of compatibility version v0.0.1; the short spelling is unchanged.|否|无|[源码差分](cases/04/repo_3.patch)|
|repo_7 / repo_13|Violates Spec 3 by ignoring read-only mode for the long --readonly spelling, allowing persistent writes.|是|test_files_and_storage.test_readonly_alias_has_same_write_behavior|[源码差分](cases/04/repo_7.patch)|


正确实现失败的测试实例包括 test_cli.test_version_contract、test_cli.test_version_alias_and_sql_version、test_cli.test_unknown_option_and_question_mark_are_errors、test_sql_and_render.test_csv_header_and_csv_escaping、test_sql_and_render.test_jsonlines_empty_and_string_newline、test_sql_and_render.test_markdown_keeps_heading_when_noheader、test_sql_and_render.test_once_persists_until_output_reset、test_sql_and_render.test_dot_version_first_two_lines、test_sql_and_render.test_dot_last_retention_only_for_truncated_duckbox、test_sql_features.test_dml_returning_and_rollback、test_sql_features.test_explain_and_geometry_roundtrip、test_sql_features.test_variant_memory_and_nth_value_zero_semantics。


## doxygen__doxygen.966d98e

### 高Mutation Score中仍有C局部预言缺口


帮助规格给出具体枚举和-x_noenv拼写；候选只检查版本标题、引导句、换行及与另一help调用相等。repo_2插入额外段落、repo_3将8)改成Eight)、repo_4将-x_noenv改成-x-noenv均存活。repo_5删除sqlite3则被test_versions杀死。实际生成配置、目录及资源的测试存在，不能将此例说成完全未执行文档业务。此例提供高分仍有局部断言缺口的对照，帮助文字与Req2Test业务角色/状态关系不同。

[完整原始规格](cases/05/requirements/spec.md)；[官方逐测试执行记录](cases/05/official-test-eval.json)；[原有结果矩阵](cases/05/failure-matrix.csv)

[spec.md](cases/05/requirements/spec.md) 第26—35行

```text
  26 
  27 `--help`, `-h`, and `-?` are successful help modes. Each writes a Doxygen version heading and the usage information to standard output; using the same help for all three is appropriate. For `--help`, standard error is empty and standard output ends with a newline. The help option has precedence: for example, `executable --help --this-flag-should-not-exist` still succeeds, emits normal help, and emits no error.
  28 
  29 Except that an implementation may substitute the actual invocation path wherever `./executable` appears, the help output is the following. Keeping it literally as shown is acceptable and is the most deterministic behavior:
  30 
  31 ```text
  32 Doxygen version 1.17.0
  33 Copyright Dimitri van Heesch 1997-2025
  34 
  35 You can use Doxygen in a number of ways:
```

[spec.md](cases/05/requirements/spec.md) 第65—77行

```text
  65 
  66    Use Doxygen to compare the used configuration file with the template configuration file
  67    without replacing the environment variables or CMake type replacement variables
  68     ./executable -x_noenv [configFile]
  69 
  70 8) Use Doxygen to show a list of built-in emojis.
  71     ./executable -f emoji outputFileName
  72 
  73     If - is used for outputFileName Doxygen will write to standard output.
  74 
  75 *) If -s is specified the comments of the configuration items in the config file will be omitted.
  76    If configName is omitted 'Doxyfile' will be used as a default.
  77    If - is used for configFile Doxygen will write / read the configuration to /from standard output / input.
```

[test_cli.py](cases/05/generated/eval/test_cli.py) 第25—52行

```text
  25 
  26 def test_help_options_and_precedence(tmp_path):
  27     for opt in ('--help', '-h', '-?'):
  28         p = invoke(tmp_path, opt)
  29         assert p.returncode == 0
  30         assert 'Doxygen version 1.17.0' in p.stdout
  31         assert 'You can use Doxygen in a number of ways:' in p.stdout
  32         assert p.stdout.endswith('\n')
  33     p = invoke(tmp_path, '--help', '--this-flag-should-not-exist')
  34     assert p.returncode == 0 and p.stderr == ''
  35     assert 'Doxygen version 1.17.0' in p.stdout
  36 
  37 
  38 def test_no_args_matches_help_and_exact_error(tmp_path):
  39     help_run = invoke(tmp_path, '--help')
  40     p = invoke(tmp_path)
  41     assert p.returncode == 1
  42     assert p.stderr == 'error: Doxyfile not found and no input file specified!\n'
  43     assert p.stdout == help_run.stdout
  44 
  45 
  46 def test_versions(tmp_path):
  47     short = invoke(tmp_path, '-v')
  48     extended = invoke(tmp_path, '-V')
  49     assert short.returncode == extended.returncode == 0
  50     assert '1.17.0' in short.stdout and '1.17.0' in extended.stdout
  51     assert 'sqlite3' in extended.stdout.lower()
  52     assert len(extended.stdout) >= len(short.stdout)
```

[test_cli.py](cases/05/generated/eval/test_cli.py) 第184—196行

```text
 184 def test_run_default_generated_config_creates_formats_and_warns(tmp_path):
 185     assert invoke(tmp_path, '-g').returncode == 0
 186     p = invoke(tmp_path)
 187     assert p.returncode == 0
 188     assert (tmp_path / 'html').is_dir() and (tmp_path / 'latex').is_dir()
 189     assert 'warning:' in p.stderr.lower() or 'No files to be processed' in p.stderr
 190 
 191 
 192 def test_run_empty_output_directory_and_disabled_formats(tmp_path):
 193     (tmp_path / 'in.cfg').write_text('OUTPUT_DIRECTORY = result\nGENERATE_HTML = NO\nGENERATE_LATEX = NO\nGENERATE_XML = NO\nGENERATE_MAN = NO\nGENERATE_RTF = NO\nGENERATE_DOCBOOK = NO\nGENERATE_PERLMOD = NO\nGENERATE_TREEVIEW = NO\n', encoding='utf-8')
 194     p = invoke(tmp_path, 'in.cfg')
 195     assert p.returncode == 0 and (tmp_path / 'result').is_dir()
 196     assert not (tmp_path / 'result' / 'html').exists()
```

### 被引用测试的实际状态


|测试实例|正确实现状态|
|---|---|
|test_cli.test_help_options_and_precedence|passed|
|test_cli.test_no_args_matches_help_and_exact_error|passed|
|test_cli.test_run_default_generated_config_creates_formats_and_warns|passed|


### 选中变异的执行结果


|binary_id / assignment_id|具体修改|有效测试杀死|杀死测试|证据|
|---|---|---|---|---|
|repo_2 / repo_3|Spec 2 violation: help generation inserts an unrequested RTF-extension paragraph, making the normalized body differ from the required baseline.|否|无|[源码差分](cases/05/repo_2.patch)|
|repo_3 / repo_4|Spec 2 violation: the eighth help mode is labeled `Eight)` instead of the required numeric `8)` enumeration.|否|无|[源码差分](cases/05/repo_3.patch)|
|repo_4 / repo_6|Spec 2 violation: help spells the no-environment comparison option as `-x-noenv` instead of `-x_noenv`.|否|无|[源码差分](cases/05/repo_4.patch)|
|repo_5 / repo_8|Spec 3 violation: extended version output identifies SQLite generically and omits the required case-sensitive `sqlite3` token.|是|test_cli.test_versions|[源码差分](cases/05/repo_5.patch)|


正确实现失败的测试实例包括 test_cli.test_run_env_expansion_in_output_path。


## simeg__eureka.df3796c

### 真实跨进程和Git状态检查的对照


test_capture_summary_preserved_commit_editor_and_main_checkout真实建立Git仓库和remote，调用程序后检查main分支、提交消息、README内容及远程commit一致。该测试在正确实现通过。前三个存活是bool参数/--后operand/普通operand接受行为，与该核心状态检查不属同一义务。CLI错误总测试本身在正确实现失败，不能推断这些存活全是有效测试弱断言。repo_4 help/version优先级变异被明确测试杀死。

[完整原始规格](cases/06/requirements/spec.md)；[官方逐测试执行记录](cases/06/official-test-eval.json)；[原有结果矩阵](cases/06/failure-matrix.csv)

[test_eureka.py](cases/06/generated/eval/test_eureka.py) 第191—203行

```text
 191 def test_capture_summary_preserved_commit_editor_and_main_checkout():
 192     with tempfile.TemporaryDirectory() as t:
 193         root=pathlib.Path(t); repo=root/'repo'; repo_init(repo,'other'); git(repo,'checkout','-b','main'); git(repo,'checkout','other')
 194         editor=root/'editor'; editor.write_text('#!/bin/sh\nprintf "edited λ\\n" >> "$1"\n'); editor.chmod(0o755)
 195         bare=root/'remote.git'; subprocess.run(['git','init','--bare',str(bare)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 196         git(repo,'remote','add','origin',str(bare))
 197         cfg=root/'cfg'; write_config(cfg,str(repo)); summary='  idea "$x" λ\\ tail  '
 198         r=run([],env={'XDG_CONFIG_HOME':str(cfg),'EDITOR':str(editor)},data=(summary+'\n').encode())
 199         assert r.returncode==0 and r.stdout==PROMPT+b'Adding and committing your new idea to main..\nAdded and committed!\nPushing your new idea..\nPushed!\n' and r.stderr==b''
 200         assert git(repo,'branch','--show-current')=='main'
 201         assert git(repo,'log','-1','--format=%s')==summary.strip()
 202         assert (repo/'README.md').read_text().endswith('edited λ\n')
 203         assert git(bare,'rev-parse','refs/heads/main')==git(repo,'rev-parse','main')
```

### 被引用测试的实际状态


|测试实例|正确实现状态|
|---|---|
|test_eureka.test_capture_summary_preserved_commit_editor_and_main_checkout|passed|


### 选中变异的执行结果


|binary_id / assignment_id|具体修改|有效测试杀死|杀死测试|证据|
|---|---|---|---|---|
|repo_1 / repo_1|Spec 1 violation: --clear-config is incorrectly implemented as an optional boolean-valued option, so attached and separate true/false values are accepted.|否|无|[源码差分](cases/06/repo_1.patch)|
|repo_2 / repo_2|Spec 1 violation: a trailing positional operand is incorrectly accepted when introduced by --.|否|无|[源码差分](cases/06/repo_2.patch)|
|repo_3 / repo_3|Spec 1 violation: the parser incorrectly declares an optional positional operand.|否|无|[源码差分](cases/06/repo_3.patch)|
|repo_4 / repo_9|Spec 2 violation: version is incorrectly given precedence when help and version are both requested.|是|test_eureka.test_help_precedence_and_cluster|[源码差分](cases/06/repo_4.patch)|


正确实现失败的测试实例包括 test_eureka.test_cli_errors_have_status_and_diagnostic、test_eureka.test_setup_preserves_lexical_absolute_paths_and_long_json。

## 对核心假设的支持程度

Pueue提供完整规格中的业务工作流覆盖缺失证据，同时有独立的帮助文本C漏检。rnr与doxygen支持“已有调用和输出观察仍可能缺少指定内容约束”，但其代表性存活涉及CLI诊断/帮助内容。它们只能支持较宽泛的断言充分性问题，尚不能作为管理员视角、跨对象业务状态缺口的同机制跨Benchmark验证。

zoxide、rnr、duckdb和eureka中的真实状态检查提供反例，尤其eureka把本地提交与远程状态关联起来。低Mutation Score无法单独证明Agent绕过了业务操作。DuckDB版本用例展示无效测试造成的判别能力丧失，本轮把它作为不同机制记录。

因此，TestSuiteBench对“规格义务可能遗漏或弱断言”的现象提供独立支持，对“与Req2Test完全相同的业务执行—观察缺口具有普遍性”仍证据不足。尚需更多匹配业务边界的已有案例及更完整运行轨迹。

