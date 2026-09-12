"""Installer workflow test for a disposable root environment.
Host operations (apt, git/CMake, users, ownership, udev and systemctl) are mocked.
File copying, package build/install, config writes, CLI and HTTP checks are real.
Does not establish native build success, OS permission behavior or USB reception.
"""
import os,sys,tempfile,subprocess,shutil,json,socket,signal
from pathlib import Path
source=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='bridge-install-test-') as tmp:
 root=Path(tmp); stage=root/'source';shutil.copytree(source,stage,ignore=shutil.ignore_patterns('.git','venv','build','*.egg-info','__pycache__'))
 opt=root/'opt';etc=root/'etc';bin=root/'bin';bin.mkdir();(etc/'systemd/system').mkdir(parents=True);(etc/'AIS-catcher/plugins').mkdir(parents=True)
 for p in stage.rglob('*'):
  if p.is_file() and p.suffix in ('.sh','.service'):
   s=p.read_text().replace('/opt/ais-atis-bridge',str(opt)).replace('/etc/',str(etc)+'/').replace('/usr/local/bin/rtl_airband',str(root/'rtl_airband'));p.write_text(s)
 log=root/'calls';pidfile=root/'pid'
 stub='''#!/usr/bin/env python3
import os,sys,subprocess,pathlib,json,signal
name=pathlib.Path(sys.argv[0]).name;a=sys.argv[1:];r=pathlib.Path(os.environ['TEST_ROOT'])
with (r/'calls').open('a') as f:f.write(json.dumps([name,*a])+'\\n')
if name in ('apt-get','getent','id','groupadd','useradd','usermod','chown','udevadm'):sys.exit(0)
if name=='install':
 b=[];i=0
 while i<len(a):
  if a[i] in ('-o','-g'):i+=2
  else:b.append(a[i]);i+=1
 sys.exit(subprocess.call(['/usr/bin/install',*b]))
if name=='runuser':sys.exit(subprocess.call(a[a.index('--')+1:]))
if name=='git':
 if a[0]=='clone':pathlib.Path(a[-1]).mkdir()
 sys.exit(0)
if name=='cmake':
 if a[0]=='--build':
  p=pathlib.Path(a[1])/'src/rtl_airband';p.parent.mkdir(parents=True);p.write_text('#!/bin/sh\\nexit 0\\n');p.chmod(0o755)
 sys.exit(0)
if name=='systemctl':
 p=r/'pid'
 if a[0]=='is-active':sys.exit(0 if p.exists() else 3)
 if a[0] in ('stop','restart') and p.exists():
  try:os.kill(int(p.read_text()),signal.SIGTERM)
  except ProcessLookupError:pass
  p.unlink()
 if a[0]=='restart':
  env=dict(os.environ,AIS_ATIS_CONFIG=str(r/'etc/ais-atis-bridge/config.json'))
  out=(r/'server.log').open('ab')
  child=subprocess.Popen([str(r/'opt/venv/bin/ais-atis-bridge')],cwd='/tmp',env=env,stdout=out,stderr=out,start_new_session=True)
  p.write_text(str(child.pid))
 sys.exit(0)
'''
 for name in ('apt-get','getent','id','groupadd','useradd','usermod','chown','udevadm','install','runuser','git','cmake','systemctl'):
  p=bin/name;p.write_text(stub);p.chmod(0o755)
 # Reuse an isolated test venv with installed dependencies; pip still builds/installs real source.
 opt.mkdir();test_venv=root/'test-venv'
 subprocess.run([sys.executable,'-m','venv','--system-site-packages',str(test_venv)],check=True)
 os.symlink(test_venv,opt/'venv')
 realpython=sys.executable
 p=bin/'python3';p.write_text('#!/bin/sh\nif [ "$1" = -m ] && [ "$2" = venv ]; then exit 0; fi\nexec '+realpython+' "$@"\n');p.chmod(0o755)
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 # Pick an isolated port through the default, leaving first-install config generation intact.
 p=stage/'ais_atis_bridge/config.py';p.write_text(p.read_text().replace('8120',str(port)))
 env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],TEST_ROOT=str(root));env.pop('PYTHONPATH',None)
 try:
  for iteration,entry in enumerate((stage/'install.sh',stage/'install.sh',opt/'install.sh')):
   result=subprocess.run(['bash',str(entry)],env=env,capture_output=True,text=True)
   if result.returncode:raise AssertionError(result.stdout+'\n'+result.stderr+'\n'+((root/'server.log').read_text() if (root/'server.log').exists() else ''))
   cfg=etc/'ais-atis-bridge/config.json';data=json.loads(cfg.read_text())
   if iteration:assert data['gain_db']==31.4
   data['gain_db']=31.4;cfg.write_text(json.dumps(data))
   print('PASS',('first install','rerun preserving config','rerun from installed directory')[iteration],flush=True)
  calls=[json.loads(x) for x in log.read_text().splitlines()]
  deps=[c for c in calls if c[0]=='apt-get' and 'libshout3-dev' in c]
  assert deps and all('libmp3lame-dev' in c for c in deps)
  assert any(c[:2]==['usermod','-a'] and 'plugdev' in c for c in calls)
  assert any(c[0]=='install' and '-o' in c and 'aisatis' in c for c in calls)
  assert (etc/'udev/rules.d/70-ais-atis-bridge.rules').exists()
  assert (etc/'AIS-catcher/plugins/ais_atis_bridge.pjs').exists()
  assert not (opt/'.git').exists()
  print('PASS dependency requests, group/ownership commands, udev/plugin placement, clean source copy')
 finally:
  if pidfile.exists():
   try:os.kill(int(pidfile.read_text()),signal.SIGTERM)
   except ProcessLookupError:pass
