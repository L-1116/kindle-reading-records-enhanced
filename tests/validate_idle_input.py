"""Real Lua mixed evdev streams + real C guard with deterministic host syscalls."""
from pathlib import Path
import datetime
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from lupa.lua51 import LuaRuntime, LuaError

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'native-reading-time-package'
sys.path.insert(0,str(ROOT/'scripts'))
from build_idle_input import ZIG, build

def tap(t):
    return [(t,0,1,330,1),(t,0,0,0,0),(t,0,1,330,0),(t,0,0,0,0)]

def key(t,code=109,source=1,value=1):
    return [(t,source,1,code,value),(t,source,0,0,0)]

def decode(folder,events,size=16,start=1000,timeout=120,clock_offset=0):
    previous=Path.cwd();os.chdir(folder)
    try:
        epoch=1728000
        stream=folder/'input'; snapshot=folder/'snapshot'
        raw=b''
        for event in events:
            if isinstance(event,int): raw+=bytes([128+event]);continue
            t,src,typ,code,value=event
            raw+=bytes([src])+struct.pack('<'+('ii' if size==16 else 'qq')+'HHi',epoch+t,0,typ,code,value)
        stream.write_bytes(raw)
        lua=LuaRuntime(); lua.globals().arg=lua.table_from({1:'-',2:str(size),3:snapshot.name,4:str(epoch+start),5:str(timeout),6:'--multiplex'})
        lua.globals().INPUT_PATH=stream.name
        lua.execute('''io.stdin=assert(io.open(INPUT_PATH,'rb')); local f=io.stdin
            io.stdin={setvbuf=function() end,read=function(_,n) local s=f:read(n)
              if s and n>1 then local a,b,c,d=s:byte(1,4); EVENT_TIME=a+b*256+c*65536+d*16777216 end
              return s end}; TEST_INPUT=f''')
        count=[]
        def rename(a,b): os.replace(a,b);count.append(1);return True
        lua.globals().os.rename=rename
        def clock(d=None):
            if d is None:return (lua.globals().EVENT_TIME or epoch+start)+clock_offset
            return time.mktime(tuple(int(d[k]) for k in ('year','month','day','hour','min','sec'))+(0,0,-1))
        lua.globals().os.time=clock
        failure=''
        try:lua.execute((PKG/'reading-idle-touch.lua').read_text(encoding='utf-8'))
        except LuaError as e:failure=str(e)
        lua.execute('TEST_INPUT:close()')
        fields=snapshot.read_text().split();fields[0]=str(int(fields[0])-epoch)
        return fields,len(count),failure
    finally:
        os.chdir(previous)

output=ROOT/'build/validation';output.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='idle-input-',dir=output) as tmp:
    folder=Path(tmp)
    for size in (16,24):
        events=tap(1060)+key(1120)+key(1120,source=2)+key(1300,value=2)+key(1301,value=0)+key(1360)
        fields,writes,error=decode(folder,events,size)
        assert fields[:2]==['1360','240'] and writes==4 and 'EOF/short read' in error,(fields,writes,error)
        # Only real press edges: volume, brightness, power, repeats, duplicate
        # down without up, release-only, connection/MSC events never resume.
        noise=sum((key(1200+i,code=c) for i,c in enumerate((115,114,224,225,116))),[])
        fields,writes,error=decode(folder,key(1060)+key(1300)+key(1350,value=2)+key(1400,value=0)+noise,size)
        assert fields[:2]==['1060','60'] and writes==2,(fields,writes)
        # Reusing a hotplug slot must discard the previous held-down state.
        fields,_,_=decode(folder,key(1060)+[1]+key(1120),size)
        assert fields[:2]==['1120','120'],fields
        fields,_,error=decode(folder,tap(1060)+[(1061,1,0,3,0)],size)
        assert fields[:2]==['1060','60'] and 'SYN_DROPPED' in error,(fields,error)
        _,_,error=decode(folder,key(1060),size,clock_offset=60)
        assert 'unsupported evdev clock' in error,error
        midnight=int(time.mktime((2026,10,22,0,0,0,0,0,-1)))-1728000
        fields,_,_=decode(folder,tap(midnight-10)+key(midnight+30),size,start=midnight-60)
        assert fields==[str(midnight+30),'90','2026-10-22','30'],fields
        fields,_,_=decode(folder,key(990)+key(1000,source=2)+tap(1005),size)
        assert fields[:2]==['1005','5'],fields
    # The same production guard is compiled with a syscall fixture, so Windows
    # can exercise its lifecycle and framing without Linux input devices.
    host=folder/('guard.exe' if os.name=='nt' else 'guard')
    compiler=[ZIG,'cc'] if Path(ZIG).is_file() or shutil.which(ZIG) else [shutil.which('cc') or 'cc']
    subprocess.run(compiler+['-std=c99','-Wall','-Wextra','-Werror','tests/idle_input_host.c','-o',str(host)],cwd=ROOT,check=True)
    subprocess.run([str(host),'.'],cwd=folder,check=True)
if Path(ZIG).is_file() or shutil.which(ZIG):
    build() # Compile real Linux headers/syscalls and verify static ARM ABI too.
else:
    # CI can run host regressions without installing the cross compiler.
    raw=(PKG/'idle-input').read_bytes()
    assert raw[:6]==b'\x7fELF\x01\x01' and int.from_bytes(raw[18:20],'little')==40
print('idle input: PASS (16/24-byte mixed touch/BT, duplicates, noise, timeout cap, midnight, reconnect, clock/stream faults; hardware pending)')
