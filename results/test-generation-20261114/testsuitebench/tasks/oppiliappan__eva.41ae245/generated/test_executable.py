import os
import subprocess
import tempfile
from pathlib import Path

BIN = Path('/workspace/executable')
if not BIN.exists():
    BIN = Path(__file__).resolve().parent.parent / 'executable'


def run(*args, input_text=None):
    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ, HOME=home)
        return subprocess.run([str(BIN), *map(str, args)], input=input_text, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=5)


def ok(expr, expected, *opts):
    p = run(*opts, expr)
    assert (p.returncode, p.stdout, p.stderr) == (0, expected + '\n', '')


def failure(expr, message, *opts):
    p = run(*opts, expr)
    assert p.returncode == 1 and p.stdout == '' and p.stderr == message + '\n'


# Spec 1, 3: command mode, version, and exact help.
def test_version_long_and_short():
    expected = 'eva 0.3.1\n'
    for opt in ('--version', '-V'):
        p = run(opt)
        assert (p.returncode, p.stdout, p.stderr) == (0, expected, '')


def test_help_exact_and_precedence():
    expected = '''Calculator REPL similar to bc(1)

Usage: executable [OPTIONS] [INPUT]

Arguments:
  [INPUT]  Optional expression string to run eva in command mode

Options:
  -f, --fix <FIX>                Number of decimal places in output (1 - 64) [default: 10]
  -b, --base <RADIX>             Radix of calculation output (1 - 36) [default: 10]
  -a, --angle_unit <angle_unit>  Angle unit [default: degree] [possible values: degree, radian, gradian]
  -h, --help                     Print help
  -V, --version                  Print version
'''
    for args in [('--help',), ('-h',), ('--help', '--version'), ('--help', '--definitely-not-a-real-flag')]:
        p = run(*args)
        assert (p.returncode, p.stdout, p.stderr) == (0, expected, '')


# Spec 2: option forms, ordering, option terminator, and argument validation.
def test_option_spellings_and_options_after_input():
    cases = [(['-f', '2', '1/3'], '0.33\n'), (['-f2', '1/3'], '0.33\n'),
             (['--fix', '2', '1/3'], '0.33\n'), (['1/3', '--fix=2'], '0.33\n'),
             (['-b', '16', '255'], ' ,   ,   , FF.0\n'), (['-b16', '255'], ' ,   ,   , FF.0\n'),
             (['--base', '16', '255'], ' ,   ,   , FF.0\n'), (['255', '--base=16'], ' ,   ,   , FF.0\n'),
             (['-a', 'radian', 'sin(pi/2)'], '1.0000000000\n'),
             (['-aradian', 'sin(pi/2)'], '1.0000000000\n'),
             (['--angle_unit', 'radian', 'sin(pi/2)'], '1.0000000000\n'),
             (['sin(pi/2)', '--angle_unit=radian'], '1.0000000000\n')]
    for args, out in cases:
        p = run(*args)
        assert (p.returncode, p.stdout, p.stderr) == (0, out, '')


def test_double_dash_and_leading_dash_expression():
    p = run('--', '-1')
    assert (p.returncode, p.stdout, p.stderr) == (0, '-1.0000000000\n', '')
    p = run('--', '--help')
    assert (p.returncode, p.stdout, p.stderr) == (1, '', 'Parser Error: Too many operators, too few operands\n')
    p = run('-5')
    assert p.returncode == 2 and p.stdout == '' and "unexpected argument '-5' found" in p.stderr


def test_multiple_positionals_and_unknown_option_diagnostics():
    p = run('2+2', '3+3')
    assert p.returncode == 2 and p.stdout == ''
    assert p.stderr == "error: unexpected argument '3+3' found\n\nUsage: executable [OPTIONS] [INPUT]\n\nFor more information, try '--help'.\n"
    p = run('--unknown-flag')
    assert p.returncode == 2 and p.stdout == ''
    assert p.stderr == "error: unexpected argument '--unknown-flag' found\n\n  tip: to pass '--unknown-flag' as a value, use '-- --unknown-flag'\n\nUsage: executable [OPTIONS] [INPUT]\n\nFor more information, try '--help'.\n"


def test_option_missing_invalid_range_and_duplicates():
    cases = [(['--fix'], "error: a value is required for '--fix <FIX>' but none was supplied\n\nFor more information, try '--help'.\n"),
             (['--base'], "error: a value is required for '--base <RADIX>' but none was supplied\n\nFor more information, try '--help'.\n"),
             (['--angle_unit'], "error: a value is required for '--angle_unit <angle_unit>' but none was supplied\n  [possible values: degree, radian, gradian]\n\nFor more information, try '--help'.\n"),
             (['--fix=abc'], "error: invalid value 'abc' for '--fix <FIX>': invalid digit found in string\n\nFor more information, try '--help'.\n"),
             (['--fix=3.5'], "error: invalid value '3.5' for '--fix <FIX>': invalid digit found in string\n\nFor more information, try '--help'.\n"),
             (['--fix=0'], "error: invalid value '0' for '--fix <FIX>': 0 is not in 1..=64\n\nFor more information, try '--help'.\n"),
             (['--fix=65'], "error: invalid value '65' for '--fix <FIX>': 65 is not in 1..=64\n\nFor more information, try '--help'.\n"),
             (['--base=37'], "error: invalid value '37' for '--base <RADIX>': 37 is not in 1..=36\n\nFor more information, try '--help'.\n"),
             (['--angle_unit=DEGREE'], "error: invalid value 'DEGREE' for '--angle_unit <angle_unit>'\n  [possible values: degree, radian, gradian]\n\nFor more information, try '--help'.\n"),
             (['--fix=2', '-f3'], "error: the argument '--fix <FIX>' cannot be used multiple times\n\nUsage: executable [OPTIONS] [INPUT]\n\nFor more information, try '--help'.\n")]
    for args, expected in cases:
        p = run(*args)
        assert (p.returncode, p.stdout, p.stderr) == (2, '', expected)


# Spec 5, 6, 7, 8: literals, precedence, associativity, implicit multiplication.
import pytest

@pytest.mark.parametrize('expr,out', [
    ('.5','0.5000000000'), ('5.','5.0000000000'), ('00012','12.0000000000'),
    ('pi','3.1415926536'), ('e','2.7182818285'), ('pi+e','5.8598744820'), ('pi*5^2','78.5398163397'),
    ('2+3*4','14.0000000000'), ('(2+3)*4','20.0000000000'), ('2^3*4','32.0000000000'),
    ('2*3^2','18.0000000000'), ('2^3^2','512.0000000000'), ('2**3**2','512.0000000000'),
    ('(2^3)^2','64.0000000000'), ('2^2^2^2','65536.0000000000'), ('5+-3','2.0000000000'),
    ('5++3','8.0000000000'), ('5--3','8.0000000000'), ('2^-1','0.5000000000'),
    ('10-5-2','3.0000000000'), ('20/4/2','2.5000000000'), ('10%3','1.0000000000'),
    ('5.5%2','1.5000000000'), ('0^0','1.0000000000'), ('2(3+4)','14.0000000000'),
    ('(2)(3)(4)','24.0000000000'), ('3sin(30)','1.5000000000'), ('2pi','6.2831853072'),
    ('5pi','15.7079632679'), ('pi2','6.2831853072'), ('e2','5.4365636569'),
    ('2pi3','18.8495559215'), ('12sin(45(2))','12.0000000000'),
], ids=lambda value: str(value)[:24])
def test_literals_operators_and_implicit_multiplication(expr,out): ok(expr,out)



def test_case_sensitive_constant_and_invalid_tokens():
    failure('PI','Parser Error: Too many operators, too few operands')
    failure('@', "Syntax Error: Unexpected token: '@'")
    failure('foo(2)', "Syntax Error: Unknown function 'foo'")
    failure('abc1', "Syntax Error: Unexpected character 'abc1'")
    failure('sin2', "Syntax Error: Function 'sin' expected parentheses")
    failure('cos3', "Syntax Error: Function 'cos' expected parentheses")
    failure('sin 30', "Syntax Error: Function 'sin' expected parentheses")
    failure('1 + co','Parser Error: Too many operators, too few operands')


def test_parentheses_and_function_argument_errors():
    for expr,out in [('(2+3','5.0000000000'), ('((1+2)*(3+4','21.0000000000'),
                    ('sin(30)+tan(45','1.5000000000'), ('ceil(sqrt(3^2+5^2','6.0000000000')]: ok(expr,out)
    for expr in ('2)','(2))','2+('): failure(expr,'Syntax Error: Mismatched parentheses!')
    failure('sqrt()','Parser Error: To few arguments for function, need 1')
    failure('log(8)','Parser Error: To few arguments for function, need 2')
    failure('nroot(23,3,4)','Parser Error: Too many operators, too few operands')
    failure('log(5,,2)','Syntax Error: Empty argument')
    failure('(1+1,2+2)','Parser Error: Too many operators, too few operands')
    failure('log(8,-2)','Parser Error: To few arguments for function, need 2')


def test_incomplete_expressions_and_factorial_unary():
    for expr in ('+','2+','1+2*','* 1+2'):
        failure(expr,'Parser Error: Too many operators, too few operands')
    failure('-1!','Domain Error: Out of bounds!')
    failure('(-1)!','Domain Error: Out of bounds!')


# Spec 9-13: functions, angle modes, factorial, numeric failures.
@pytest.mark.parametrize('expr,out', [
 ('sqrt(2)','1.4142135624'),('sinh(1)','1.1752011936'),('cosh(1)','1.5430806348'),('tanh(1)','0.7615941560'),
 ('exp(3)','20.0855369232'),('exp2(8)','256.0000000000'),('log(8,2)','3.0000000000'),('nroot(27,3)','3.0000000000'),
 ('rad(180)','3.1415926536'),('deg(pi)','180.0000000000'),('exp(ln(5))','5.0000000000'),
 ('floor(sqrt(3^2+5^2))','5.0000000000'),('log(1+(2^16),4)','8.0000110068'),('nroot(2+2,4+e^2)','1.1294396449'),
 ('round(0.5)','1.0000000000'),('round(3.5)','4.0000000000'),('round(-2.5)','-3.0000000000'),('round(2.4)','2.0000000000'),
 ('ceil(-3.2)','-3.0000000000'),('floor(-3.8)','-4.0000000000'),('0!','1.0000000000'),('5!','120.0000000000'),
 ('(2+3)!','120.0000000000'),('20!','2,432,902,008,176,640,000.0000000000'),('21!','51,090,942,171,709,440,000.0000000000'),('3!!','720.0000000000'),
], ids=lambda value: str(value)[:24])
def test_functions_rounding_and_factorial(expr,out): ok(expr,out)


def test_factorial_large_binary64_and_overflow():
    ok('5!!','6,689,502,913,449,123,933,681,342,530,579,439,120,523,775,756,341,546,089,360,093,784,620,090,324,126,011,858,610,763,674,005,344,861,930,779,387,322,735,825,049,576,193,801,545,269,664,994,272,835,560,837,966,773,424,760,538,449,951,889,918,907,707,412,713,570,304.0000000000')
    for expr in ('5%0','10^1000','2^10000','10^500*10^500','171!','200!','1000!'):
        failure(expr,'Error: to large to process! Max value: 179769313486231570000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000')
    for expr,out in [('2^1000','107150860718626732094842504906000181056140481170553360744375038837035105112493612249319837881569585812759467291755314682518714528569231404359768703014224035430129155037707237185908252704092710626996628107361613047767363983770001764293167634028795081680356207607191539887597942576279375594311022102440'),('exp(700)',None),('120!',None)]:
        p=run(expr); assert p.returncode==0 and p.stdout.endswith('\n') and p.stderr==''


def test_division_zero_and_function_domains():
    failure('1/0','Math Error: Divide by zero error!')
    failure('1+(2/0)','Math Error: Divide by zero error!')
    for expr in ('sqrt(-1)','ln(0)','ln(-1)','log2(0)','log10(-2)','asin(2)','acos(-2)','nroot(-8,3)','(-1)!','1.5!','exp(1000)','1+sqrt(-1)','log(-2,2)','log(2,1)'):
        failure(expr,'Domain Error: Out of bounds!')


def test_forward_and_inverse_trigonometry_modes():
    cases=[([], 'sin(30)','0.5000000000'),([], 'sin(90)','1.0000000000'),([], 'cos(60)','0.5000000000'),([], 'tan(45)','1.0000000000'),([], 'csc(30)','2.0000000000'),([], 'sec(60)','2.0000000000'),([], 'cot(45)','1.0000000000'),
    (['--angle_unit','radian'],'sin(pi/2)','1.0000000000'),(['--angle_unit','radian'],'cos(pi)','-1.0000000000'),(['--angle_unit','radian'],'tan(pi/4)','1.0000000000'),
    (['--angle_unit=gradian'],'sin(100)','0.9848077530'),([], 'asin(0.5)','0.5235987756'),([], 'acos(0.5)','1.0471975512'),([], 'atan(1)','0.7853981634'),([], 'acsc(2)','0.5235987756'),([], 'asec(2)','1.0471975512'),([], 'acot(1)','0.7853981634'),([], 'deg(asin(1))','90.0000000000')]
    for opts,expr,out in cases: ok(expr,out,*opts)


# Spec 15-17 formatting and calculator help.
def test_decimal_fixed_format_and_binary64_rounding():
    cases=[('1/3','0.3333333333',()),('1/3','0.33',('--fix','2')),('2/3','0.667',('--fix','3')),('1/2','0.50000',('--fix','5')),
    ('0.000001','0.00',('--fix','2')),('999.999','1,000.0',('--fix','1')),('1234567.89','1,234,567.8899999999',()),('1000000','1,000,000.0000000000',()),
    ('1/3','0.33333333333333331483',('--fix','20')),('1/3','0.3333333333333333148296162562473909929394721984863281250000000000',('--fix','64')),
    ('1/7','0.14285714285714284921',('--fix','20')),('pi','3.141592653589793115997963468544',('--fix','30')),('e','2.7182818284590450907955983',('--fix','25')),('-0','0.0000000000',())]
    for expr,out,opts in cases: ok(expr,out,*opts)


def test_radix_conversion_and_layout():
    cases=[(['--base','16'],'255',' ,   ,   , FF.0'),(['--base','2'],'15',' ,   ,  1,111.0'),(['--base','16'],'4095',' ,   ,   ,FFF.0'),(['--base','16'],'0-255',' ,   ,   ,-FF.0'),(['--base','2'],'1024','10,000,000,000.0'),(['--base','36'],'1000',' ,   ,   , RS.0'),
    (['--base','8'],'255',' ,   ,   , 377.0'),(['--base','16'],'256',' ,   ,   , 100.0'),(['--base','3'],'10',' ,   ,   , 101.0'),(['--base','5'],'25',' ,   ,   , 100.0'),(['--base','26'],'100',' ,   ,   , 3M.0'),
    (['--base','2'],'0.5',' ,   ,   ,   0.1'),(['--base','8'],'0.125',' ,   ,   ,   0.1'),(['--base','16'],'0.25',' ,   ,   ,   0.4'),(['--base','16'],'15.9375',' ,   ,   ,  F.F'),(['--fix','1','--base','16'],'1/3',' ,   ,   ,   0.4')]
    for opts,expr,out in cases: ok(expr,out,*opts)
    ok('0.5',' ,   ,   ,   0.1','--base','2','--fix','10')


def test_calculator_help_command_and_repl_summary():
    p=run('help')
    assert p.returncode==1 and p.stdout==''
    for heading in ('Constants','Functions','Operators'):
        assert heading in p.stderr
    for name in 'pi e deg tan sinh abs rad sin floor cot exp ceil sqrt log sec asin acsc exp2 asec tanh log10 acot round log2 acos csc ln nroot atan cos cosh'.split():
        assert name in p.stderr.split()
    for op in '- + / % * ^ !'.split(): assert op in p.stderr.split()


# Spec 18: piped REPL behavior and previous answer/history.
def test_piped_repl_sequences_blank_line_and_recovery():
    with tempfile.TemporaryDirectory() as home:
        p=subprocess.run([str(BIN)],input='5 + 3\n\n1/0\n2+2\n',text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,HOME=home),timeout=5)
    assert p.returncode==0 and p.stderr==''
    lines=p.stdout.splitlines()
    assert lines[-4:]==['8.0000000000','0.0000000000','Math Error: Divide by zero error!','4.0000000000']


def test_repl_previous_answer_and_zero():
    with tempfile.TemporaryDirectory() as home:
        p=subprocess.run([str(BIN)],input='5*5\n_ + 10\n_*2\n0\n_+1\n',text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,HOME=home),timeout=5)
    assert p.returncode==0 and p.stderr==''
    assert p.stdout.splitlines()[-5:]==['25.0000000000','35.0000000000','70.0000000000','0.0000000000','1.0000000000']


def test_repl_help_is_informational_and_does_not_change_numeric_flags():
    with tempfile.TemporaryDirectory() as home:
        p=subprocess.run([str(BIN),'--fix','2'],input='help\n1/3\n',text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,HOME=home),timeout=5)
    assert p.returncode==0 and p.stderr==''
    assert 'Constants' in p.stdout and 'Functions' in p.stdout and 'Operators' in p.stdout
    assert p.stdout.endswith('0.33\n')


def test_repl_history_persists_by_home_and_command_has_no_notice():
    with tempfile.TemporaryDirectory() as home:
        env=dict(os.environ,HOME=home)
        first=subprocess.run([str(BIN)],input='2+2\n',text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=5)
        second=subprocess.run([str(BIN)],input='3+3\n',text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=5)
        command=subprocess.run([str(BIN),'1+1'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=5)
    assert first.returncode==second.returncode==command.returncode==0
    assert 'No previous history.\n' in first.stdout
    assert 'No previous history.' not in second.stdout and second.stdout.endswith('6.0000000000\n')
    assert command.stdout=='2.0000000000\n' and command.stderr==''
