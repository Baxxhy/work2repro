"""Small protocol bots used by the evaluation suite."""
import sys
import time

mode = sys.argv[1] if len(sys.argv) > 1 else 'empty'
label = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else mode.capitalize() + 'Bot'
try:
    player = sys.stdin.readline().rstrip('\n')
    dims = sys.stdin.readline().split()
    width, height = map(int, dims)
    production = sys.stdin.readline().split()
    initial = sys.stdin.readline()
    if mode == 'init_sleep':
        time.sleep(5)
    if mode != 'empty_name':
        print(label, flush=True)
    else:
        print('', flush=True)
    turn = 0
    while True:
        state = sys.stdin.readline()
        if not state:
            break
        turn += 1
        if mode == 'turn_sleep' and turn == 1:
            time.sleep(5)
        elif mode == 'crash' and turn == 1:
            sys.exit(2)
        elif mode == 'invalid' and turn == 1:
            print('not a move', flush=True)
        elif mode == 'east':
            # Send legal triples for every board location.
            print(' '.join(f'{x} {y} 2' for y in range(height) for x in range(width)), flush=True)
        else:
            print('', flush=True)
except Exception:
    pass
