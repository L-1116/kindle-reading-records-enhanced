"""Real Lua 5.1 render/syntax with explicit mock evdev hardware boundary."""
from pathlib import Path
import os
import sys
import time
from lupa.lua51 import LuaRuntime

def native(value):
    if value and os.name == 'nt' and len(value) > 3 and value[0] == '/' and value[2] == '/' and value[1].isalpha():
        return value[1].upper() + ':' + value[2:]
    return value

args = sys.argv[1:]
target = Path(args[0]).name
if target == 'reading-insights-touch-probe.lua':
    print(os.environ['READING_TOUCH_DEVICE'])
    print('16\nunknown\nunknown\nunknown\nunknown\nauto')
    raise SystemExit(0)
if target in ('reading-insights-touch-ui.lua', 'reading-insights-touch.lua'):
    # Mock read-only input initialization only after the complete-page refresh.
    with open(native(args[1]), 'rb'):
        pass
    if os.environ.get('READING_PERF') == '1' and not os.environ.get('READING_PERF_READY_DONE'):
        with open(native(os.environ['READING_PERF_LOG']), 'a') as log:
            log.write(f'stage=software_interactive_ready uptime={time.monotonic():.6f} source=MOCK_INPUT\n')
    print('exit')
    raise SystemExit(0)
lua = LuaRuntime(unpack_returned_tuples=True)
def fopen(path, mode='r'):
    return original_open(native(path), mode)
original_open = lua.globals().io.open
lua.globals().io.open = fopen
if target == '-e':
    # loadfile is genuine; convert only the host sandbox path convention.
    loadfile = lua.globals().loadfile
    lua.globals()._python_loadfile = lambda path: loadfile(native(path))
    lua.execute("loadfile=function(path) return _python_loadfile(path) end")
    lua.execute(args[1])
else:
    lua.globals().arg = lua.table_from({i: native(value) for i,value in enumerate(args)})
    lua.execute(Path(native(args[0])).read_text(encoding='utf-8'))
