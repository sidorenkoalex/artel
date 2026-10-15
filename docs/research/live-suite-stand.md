# Подготовка live-стенда Codex/Claude × macOS/Linux

Решение Оператора 15.10.2026: вариант A, подготовить стенд до продолжения test_author задачи 01M4XVM49PP5WHSXT5S8JW85WN. Бюджет задачи $45 не изменён. Реальные четыре production-маршрута пока НЕ доказаны. Платных вызовов моделей при этой подготовке не было.

Нативные Linux arm64 CLI проверены по npm integrity SHA-512: Codex 0.157.1, Claude 2.1.283. Docker-образ подготовлен без учётных данных и каталогов хоста. Контейнеры строителей удаляются в finally. Docker default seccomp запрещает unshare NEWUSER; узкие бесплатные эксперименты разрешили только точный unshare NEWUSER и точный clone 0x7e020011. Bubblewrap затем упёрся в mount MS_SLAVE|MS_REC|MS_SILENT (EPERM). mount, SYS_ADMIN, privileged, unconfined и слабый sandbox не разрешались. Диагностика не является доказательством production-политики.

Следующий локальный маршрут — отдельная Linux VM через macOS Virtualization.framework (2 CPU, 2 GiB, собственный диск, NAT, без host mounts). Swift launcher с entitlement com.apple.security.virtualization скомпилирован. Создание гостевого диска выполняется отдельным собственным контейнером без mount: экспорт rootfs и mkfs.ext4 -d. Подготовка и загрузка VM ещё требуют проверки. SSH-ключ эфемерный; секретная часть не публикуется.

Воспроизведение: fetch-native.py; build-local.py; vm/build-vm.py; swiftc -framework Virtualization vm/run-vm.swift -o vm/run-vm; codesign --force --sign - --entitlements vm/entitlements.plist vm/run-vm; vm/run-vm vm. Команды выполняются в отдельном временном каталоге. Для повторного создания VM нужен новый каталог, поскольку ssh-keygen не перезаписывает ключ.

Для завершения нужны: четыре настоящих provider exec с production-политикой, kernel peer identity и ancestry/lease, положительный ровно один Unix-сокет и отрицательные sibling Unix/TCP/UDP/IPv6/domain/process проверки, сбор доказательств и штатный учёт стоимости. Preflight всегда ready_for_live=false до этих результатов.

Официальные источники: [Codex config](https://learn.chatgpt.com/docs/config-file/config-reference), [Claude sandbox](https://code.claude.com/docs/en/sandboxing), [Moby seccomp](https://github.com/moby/profiles/blob/6fe7deb1b9fb7c0397a4593480d7d22b9ee8caef/seccomp/default.json). Профиль Moby не объявляется идентичным встроенному профилю Docker 28.4.

## Исходники подготовки

### fetch-native.py

```python
import base64,hashlib,io,json,os,tarfile,urllib.request,time
from pathlib import Path
root=Path(__file__).resolve().parent
(root/'native').mkdir(exist_ok=True)
for name,meta_file in [('codex','codex-native-package.json'),('claude','claude-code-linux-arm64-native-package.json')]:
    meta=json.loads((root/meta_file).read_text())
    req=urllib.request.Request(meta['dist']['tarball'],headers={'User-Agent':'artel-live-stand-preflight'})
    digest=hashlib.sha512(); chunks=[]; size=0; started=time.monotonic(); reported=0
    with urllib.request.urlopen(req,timeout=45) as response:
        while True:
            chunk=response.read(1024*1024)
            if not chunk:break
            size+=len(chunk)
            if time.monotonic()-started>240:raise TimeoutError('package download exceeded 240s')
            if size-reported>=16*1024*1024:
                print(json.dumps({'cli':name,'downloaded':size}),flush=True);reported=size
            if size>256*1024*1024:raise RuntimeError('package too large')
            digest.update(chunk);chunks.append(chunk)
    actual='sha512-'+base64.b64encode(digest.digest()).decode()
    assert actual==meta['dist']['integrity'],'integrity mismatch'
    with tarfile.open(fileobj=io.BytesIO(b''.join(chunks)),mode='r:gz') as archive:
        candidates=[m for m in archive.getmembers() if m.isfile() and Path(m.name).name in (name,name+'.exe')]
        assert len(candidates)==1,[(m.name,m.size) for m in candidates]
        data=archive.extractfile(candidates[0]).read();assert data.startswith(b'\x7fELF')
        target=root/'native'/name;target.write_bytes(data);target.chmod(0o755)
    meta['download_bytes']=size;meta['native_sha256']=hashlib.sha256(data).hexdigest();meta['native_size']=len(data)
    (root/(name+'-verified.json')).write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps({'cli':name,'version':meta['version'],'native_sha256':meta['native_sha256'],'size':len(data)}),flush=True)

```

### build-local.py

```python
import json,subprocess,uuid
from pathlib import Path
root=Path(__file__).resolve().parent
name='artel-live-stand-build-'+uuid.uuid4().hex[:10]
tag='artel-live-stand:codex-0.157.1-claude-2.1.283'
def run(args,limit=90):
    p=subprocess.run(args,capture_output=True,text=True,timeout=limit)
    if p.returncode:raise RuntimeError(str(args[:4])+': '+(p.stderr or p.stdout)[-1200:])
    return p.stdout.strip()
cid=None
try:
    cid=run(['docker','create','--pull','never','--label','artel.operator.live-stand=true','--name',name,'python:3.13','sleep','900'])
    (root/'builder.json').write_text(json.dumps({'id':cid,'name':name,'tag':tag})+'\n')
    run(['docker','start',cid]);print('builder_started '+cid[:12],flush=True)
    run(['docker','exec',cid,'python3','-c',"from pathlib import Path; [(p.write_text(p.read_text().replace('http://','https://'))) for p in Path('/etc/apt/sources.list.d').glob('*.sources')]"]); run(['docker','exec',cid,'apt-get','-o','Acquire::Retries=0','-o','Acquire::https::Timeout=10','update'],60);print('apt_index_ready',flush=True)
    run(['docker','exec',cid,'apt-get','install','-y','--no-install-recommends','bubblewrap','socat','libseccomp2']);print('sandbox_dependencies_ready',flush=True)
    for binary in ('codex','claude'):
        assert (root/'native'/binary).is_file(),'native download not ready: '+binary
        run(['docker','cp',str(root/'native'/binary),cid+':/usr/local/bin/'+binary])
        print(run(['docker','exec',cid,binary,'--version']),flush=True)
    run(['docker','exec',cid,'useradd','--uid','1000','--create-home','agent'])
    run(['docker','exec',cid,'mkdir','-p','/work'])
    run(['docker','exec',cid,'chown','1000:1000','/work'])
    run(['docker','cp',str(root/'preflight.py'),cid+':/work/preflight.py'])
    image=run(['docker','commit','--change','USER agent','--change','WORKDIR /work','--change','ENV HOME=/home/agent',cid,tag])
    (root/'image.json').write_text(json.dumps({'image':image,'tag':tag,'base':'python:3.13','builder':cid})+'\n')
    print('image_ready '+image,flush=True)
finally:
    if cid:
        p=subprocess.run(['docker','rm','--force',cid],capture_output=True,text=True,timeout=20)
        print('own_builder_removed='+str(p.returncode==0),flush=True)

```

### preflight.py

```python
import ctypes,json,os,platform,shutil,subprocess

def version(cmd):
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
        return {'rc':p.returncode,'version':(p.stdout+p.stderr).strip()[:300]}
    except Exception as e:return {'error':type(e).__name__}
lib=ctypes.CDLL(None,use_errno=True)
userns={'available':None}
if platform.system()=='Linux':
    # Run in a child: the preflight process keeps its own namespace.
    child=subprocess.run(['python3','-c','import ctypes,json; l=ctypes.CDLL(None,use_errno=True); r=l.unshare(0x10000000); print(json.dumps({"rc":r,"errno":ctypes.get_errno()}))'],capture_output=True,text=True,timeout=10)
    userns=json.loads(child.stdout) if child.returncode==0 else {'error':'child_failed'}
result={'schema':1,'platform':platform.system(),'machine':platform.machine(),'uid':os.getuid(),'userns':userns,'tools':{n:version([n,'-V' if n=='socat' else '--version']) if shutil.which(n) else {'error':'missing'} for n in (('codex','claude','bwrap','socat','python3') if platform.system()=='Linux' else ('codex','claude','python3'))}}

if platform.system()=='Linux':
    result['bubblewrap_smoke']=version(['bwrap','--unshare-all','--new-session','--ro-bind','/','/','--proc','/proc','--dev','/dev','/usr/bin/true'])
result['live_evidence']=False
result['dependencies_ready']=not any('error' in v or v.get('rc',0)!=0 for v in result['tools'].values()) and (platform.system()!='Linux' or (userns.get('rc')==0 and result.get('bubblewrap_smoke',{}).get('rc')==0))
result['ready_for_live']=False
result['production_policy_verified']=False
print(json.dumps(result,ensure_ascii=False,sort_keys=True))

```

### image.json

```
{"image": "sha256:87f3d797dfcd90e8ae83341b8326ac5d3eba65ee59ec15781216a82fc59b609c", "tag": "artel-live-stand:codex-0.157.1-claude-2.1.283", "base": "python:3.13", "builder": "0175820db2df25d9a0cb4d74c1831212cd80d07391a527d5dd35b624a94fe558"}

```

### codex-verified.json

```
{
  "name": "@openai/codex",
  "version": "0.157.1-linux-arm64",
  "dist": {
    "shasum": "f1a489ec755036797d5356545640b3bba13a421e",
    "tarball": "https://registry.npmjs.org/@openai/codex/-/codex-0.157.1-linux-arm64.tgz",
    "fileCount": 46,
    "integrity": "sha512-nEaBZT3ldrtqUNaBlvI+Y+fg+LbNCTsQjbUnl7Q45rl9vSSqHU2vRj1l6iJDwupZkrpeIJ/ClHIwxgMKv1SKHg==",
    "signatures": [
      {
        "sig": "MEUCIQDwraDmCQuNJv60p+PB9Cuya1V+UkfqHvHUTYHhKKev1AIgZG4ROS6MIN3aKWKFlqBiruy8OrpHrtkT8nlKqaFE3/Y=",
        "keyid": "SHA256:DhQ8wR5APBvFHLF/+Tc+AYvPOdTpcIDqOhxsBHRwC7U"
      },
      {
        "sig": "MEUCIQDaL/ZI6O08/IeP0cgY8rQhXSPNhFpkfU4DjR+Gpj6qZAIgI7ycFRXJz2/i0YlEP2L9JyLjPMIgYsFLEw2LmldxZV4=",
        "keyid": "SHA256:DhQ8wR5APBvFHLF/+Tc+AYvPOdTpcIDqOhxsBHRwC7U"
      }
    ],
    "attestations": {
      "url": "https://registry.npmjs.org/-/npm/v1/attestations/@openai%2fcodex@0.157.1-linux-arm64",
      "provenance": {
        "predicateType": "https://slsa.dev/provenance/v1"
      }
    },
    "unpackedSize": 345038028
  },
  "download_bytes": 142975101,
  "native_sha256": "9cbc3cdcc18ca336523ffa7d64207a1ae1f5991f823081d0a37bcb3a748de093",
  "native_size": 246724968
}

```

### claude-verified.json

```
{
  "name": "@anthropic-ai/claude-code-linux-arm64",
  "version": "2.1.283",
  "dist": {
    "shasum": "efc347281422c89e4b67f1903ac975d3892767fc",
    "tarball": "https://registry.npmjs.org/@anthropic-ai/claude-code-linux-arm64/-/claude-code-linux-arm64-2.1.283.tgz",
    "fileCount": 4,
    "integrity": "sha512-1hGh4eQHoxNJSfA/0/id5lXFdO5yRScwtUlBNMu1fPxUSwiFosLQjPDv/KdgfVZ3xjVtqJWPbjtKQ1TsxfpcDg==",
    "signatures": [
      {
        "sig": "MEYCIQCYUqYQLvU7Hm7KIGpnABDKukCTymwrzP6U2UCR4LIqNAIhAPzb1pn0l1eSokfaGtKqr6TKJi9/cDsTTj8w/d2G9Mia",
        "keyid": "SHA256:DhQ8wR5APBvFHLF/+Tc+AYvPOdTpcIDqOhxsBHRwC7U"
      },
      {
        "sig": "MEUCIHwV35BajAcjEzq2OSG7iiycunKI7wvDrtDhaUoKs4u/AiEAnhs8pwAkxMNaxvaAgikO7DONniXAeuf8B4In3YJWr08=",
        "keyid": "SHA256:DhQ8wR5APBvFHLF/+Tc+AYvPOdTpcIDqOhxsBHRwC7U"
      }
    ],
    "unpackedSize": 240902730
  },
  "download_bytes": 108771563,
  "native_sha256": "346d294f0103d6fc0de11ac953579b5c62dfa90698a4cfc486b6f927c615e697",
  "native_size": 240902136
}

```

### vm/build-vm.py

```python
import subprocess,uuid,json
from pathlib import Path
root=Path(__file__).resolve().parent
cid=None
def run(args,timeout=180):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 if p.returncode:raise RuntimeError((p.stderr or p.stdout)[-2500:])
 return p.stdout.strip()
try:
 cid=run(['docker','create','--user','root','--label','artel.operator.live-stand=true','--name','artel-live-vm-'+uuid.uuid4().hex[:8],'artel-live-stand:codex-0.157.1-claude-2.1.283','sleep','1800'])
 run(['docker','start',cid]);print('own_vm_builder_started',flush=True)
 run(['docker','exec',cid,'apt-get','-o','Acquire::Retries=0','-o','Acquire::https::Timeout=15','update'])
 run(['docker','exec',cid,'env','DEBIAN_FRONTEND=noninteractive','apt-get','install','-y','--no-install-recommends','linux-image-arm64','initramfs-tools','systemd-sysv','systemd-resolved','openssh-server','e2fsprogs'],600)
 print('guest_kernel_installed',flush=True)
 run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(root/'id_ed25519')])
 pub=(root/'id_ed25519.pub').read_text().strip()
 setup="""from pathlib import Path
import subprocess
Path('/etc/fstab').write_text('/dev/vda / ext4 defaults 0 1\\n')
Path('/etc/systemd/network/20-wired.network').write_text('[Match]\\nName=en* eth*\\n[Network]\\nDHCP=yes\\n')
Path('/etc/ssh/sshd_config.d/stand.conf').write_text('PasswordAuthentication no\\nPermitRootLogin no\\n')
p=Path('/home/agent/.ssh');p.mkdir(mode=0o700,exist_ok=True)
(p/'authorized_keys').write_text(PUB+'\\n');(p/'authorized_keys').chmod(0o600)
subprocess.run(['chown','-R','1000:1000',str(p)],check=True)
subprocess.run(['systemctl','enable','systemd-networkd','systemd-resolved','ssh'],check=True)
""".replace('PUB',repr(pub))
 run(['docker','exec',cid,'python3','-c',setup])
 run(['docker','cp',str(root.parent/'preflight.py'),cid+':/work/preflight.py'])
 kernel=run(['docker','exec',cid,'sh','-c','ls /boot/vmlinuz-*']).splitlines()[-1]
 initrd=run(['docker','exec',cid,'sh','-c','ls /boot/initrd.img-*']).splitlines()[-1]
 run(['docker','cp',cid+':'+kernel,str(root/'vmlinuz')])
 run(['docker','cp',cid+':'+initrd,str(root/'initrd.img')])
 run(['docker','exec',cid,'mkdir','-p','/vm-export/root'])
 # Export from outside the source tree; no mounts or elevated container capabilities.
 subprocess.run(['docker','export','-o',str(root/'rootfs.tar'),cid],check=True,timeout=120)
 run(['docker','cp',str(root/'rootfs.tar'),cid+':/vm-export/rootfs.tar'])
 run(['docker','exec',cid,'tar','-xf','/vm-export/rootfs.tar','-C','/vm-export/root'],120)
 run(['docker','exec',cid,'truncate','-s','6G','/vm-export/root.raw'])
 run(['docker','exec',cid,'mkfs.ext4','-q','-F','-d','/vm-export/root','/vm-export/root.raw'],180)
 run(['docker','cp',cid+':/vm-export/root.raw',str(root/'root.raw')],180)
 print('guest_disk_ready',flush=True)
finally:
 if cid:print('own_vm_builder_removed='+str(subprocess.run(['docker','rm','-f',cid],capture_output=True,timeout=30).returncode==0),flush=True)

```

### vm/run-vm.swift

```
import Foundation
import Virtualization

let root = URL(fileURLWithPath: CommandLine.arguments[1])
let config = VZVirtualMachineConfiguration()
let boot = VZLinuxBootLoader(kernelURL: root.appendingPathComponent("vmlinuz"))
boot.initialRamdiskURL = root.appendingPathComponent("initrd.img")
boot.commandLine = "root=/dev/vda rw console=hvc0 net.ifnames=0"
config.bootLoader = boot
config.cpuCount = 2
config.memorySize = 2 * 1024 * 1024 * 1024
let attachment = try VZDiskImageStorageDeviceAttachment(url: root.appendingPathComponent("root.raw"), readOnly: false)
config.storageDevices = [VZVirtioBlockDeviceConfiguration(attachment: attachment)]
let network = VZVirtioNetworkDeviceConfiguration()
network.macAddress = VZMACAddress(string: "02:7a:17:00:00:17")!
network.attachment = VZNATNetworkDeviceAttachment()
config.networkDevices = [network]
let serial = VZVirtioConsoleDeviceSerialPortConfiguration()
serial.attachment = VZFileHandleSerialPortAttachment(fileHandleForReading: FileHandle.standardInput, fileHandleForWriting: FileHandle.standardOutput)
config.serialPorts = [serial]
config.entropyDevices = [VZVirtioEntropyDeviceConfiguration()]
try config.validate()
let machine = VZVirtualMachine(configuration: config)
machine.start { result in
    switch result {
    case .success: print("ARTEL_VM_STARTED")
    case .failure(let error): print("ARTEL_VM_ERROR: \(error)"); exit(1)
    }
}
RunLoop.main.run()

```

### vm/entitlements.plist

```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>com.apple.security.virtualization</key><true/></dict></plist>

```

## Проверка загрузки VM (15.10, 06:20 UTC)

VM загрузилась с ядром 6.12.111+deb13-arm64, отдельный собственный root.raw 6 GiB. От UID 1000 реально выполнен preflight: Codex 0.157.1, Claude 2.1.283, Python 3.13.15, bubblewrap 0.12.0, socat 1.8.0.3; unshare NEWUSER rc=0 и bubblewrap smoke rc=0 без ослабленного Docker/seccomp. Это проверка зависимостей, не production/live evidence: ready_for_live=false.

При экспорте rootfs Docker оставил /.dockerenv и пустой /etc/resolv.conf. В собственном госте marker удалён, resolv.conf заменён стандартной ссылкой systemd-resolved; изменения добавлены в build-vm.py для повторения. Для диагностики использовалась локальная serial-консоль через временный root autologin; он удалён после диагностики. SSH с хоста к выданному гостю DHCP адресу 192.168.64.2 пока завершился timeout, причина не установлена. Консоль работает. Маршрут нельзя считать готовым для ролей до проверки транспорта, сети, политики, учёта стоимости и четырёх реальных CLI результатов.

### Актуальная версия vm/build-vm.py

```
import subprocess,uuid,json
from pathlib import Path
root=Path(__file__).resolve().parent
cid=None
def run(args,timeout=180):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 if p.returncode:raise RuntimeError((p.stderr or p.stdout)[-2500:])
 return p.stdout.strip()
try:
 cid=run(['docker','create','--user','root','--label','artel.operator.live-stand=true','--name','artel-live-vm-'+uuid.uuid4().hex[:8],'artel-live-stand:codex-0.157.1-claude-2.1.283','sleep','1800'])
 run(['docker','start',cid]);print('own_vm_builder_started',flush=True)
 run(['docker','exec',cid,'apt-get','-o','Acquire::Retries=0','-o','Acquire::https::Timeout=15','update'])
 run(['docker','exec',cid,'env','DEBIAN_FRONTEND=noninteractive','apt-get','install','-y','--no-install-recommends','linux-image-arm64','initramfs-tools','systemd-sysv','systemd-resolved','openssh-server','e2fsprogs'],600)
 print('guest_kernel_installed',flush=True)
 run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(root/'id_ed25519')])
 pub=(root/'id_ed25519.pub').read_text().strip()
 setup="""from pathlib import Path
import subprocess
Path('/.dockerenv').unlink(missing_ok=True)
Path('/etc/resolv.conf').unlink(missing_ok=True)
Path('/etc/resolv.conf').symlink_to('/run/systemd/resolve/stub-resolv.conf')
Path('/etc/fstab').write_text('/dev/vda / ext4 defaults 0 1\\n')
Path('/etc/systemd/network/20-wired.network').write_text('[Match]\\nName=en* eth*\\n[Network]\\nDHCP=yes\\n')
Path('/etc/ssh/sshd_config.d/stand.conf').write_text('PasswordAuthentication no\\nPermitRootLogin no\\n')
p=Path('/home/agent/.ssh');p.mkdir(mode=0o700,exist_ok=True)
(p/'authorized_keys').write_text(PUB+'\\n');(p/'authorized_keys').chmod(0o600)
subprocess.run(['chown','-R','1000:1000',str(p)],check=True)
subprocess.run(['systemctl','enable','systemd-networkd','systemd-resolved','ssh'],check=True)
""".replace('PUB',repr(pub))
 run(['docker','exec',cid,'python3','-c',setup])
 run(['docker','cp',str(root.parent/'preflight.py'),cid+':/work/preflight.py'])
 kernel=run(['docker','exec',cid,'sh','-c','ls /boot/vmlinuz-*']).splitlines()[-1]
 initrd=run(['docker','exec',cid,'sh','-c','ls /boot/initrd.img-*']).splitlines()[-1]
 run(['docker','cp',cid+':'+kernel,str(root/'vmlinuz')])
 run(['docker','cp',cid+':'+initrd,str(root/'initrd.img')])
 run(['docker','exec',cid,'mkdir','-p','/vm-export/root'])
 # Export from outside the source tree; no mounts or elevated container capabilities.
 subprocess.run(['docker','export','-o',str(root/'rootfs.tar'),cid],check=True,timeout=120)
 run(['docker','cp',str(root/'rootfs.tar'),cid+':/vm-export/rootfs.tar'])
 run(['docker','exec',cid,'tar','-xf','/vm-export/rootfs.tar','-C','/vm-export/root'],120)
 run(['docker','exec',cid,'truncate','-s','6G','/vm-export/root.raw'])
 run(['docker','exec',cid,'mkfs.ext4','-q','-F','-d','/vm-export/root','/vm-export/root.raw'],180)
 run(['docker','cp',cid+':/vm-export/root.raw',str(root/'root.raw')],180)
 print('guest_disk_ready',flush=True)
finally:
 if cid:print('own_vm_builder_removed='+str(subprocess.run(['docker','rm','-f',cid],capture_output=True,timeout=30).returncode==0),flush=True)

```

### Актуальная версия vm/run-vm.swift

```
import Foundation
import Virtualization

let root = URL(fileURLWithPath: CommandLine.arguments[1])
let config = VZVirtualMachineConfiguration()
let boot = VZLinuxBootLoader(kernelURL: root.appendingPathComponent("vmlinuz"))
boot.initialRamdiskURL = root.appendingPathComponent("initrd.img")
boot.commandLine = "root=/dev/vda rw console=hvc0 net.ifnames=0" + (CommandLine.arguments.contains("--repair") ? " init=/bin/sh" : "")
config.bootLoader = boot
config.cpuCount = 2
config.memorySize = 2 * 1024 * 1024 * 1024
let attachment = try VZDiskImageStorageDeviceAttachment(url: root.appendingPathComponent("root.raw"), readOnly: false)
config.storageDevices = [VZVirtioBlockDeviceConfiguration(attachment: attachment)]
let network = VZVirtioNetworkDeviceConfiguration()
network.macAddress = VZMACAddress(string: "02:7a:17:00:00:17")!
network.attachment = VZNATNetworkDeviceAttachment()
config.networkDevices = [network]
let serial = VZVirtioConsoleDeviceSerialPortConfiguration()
serial.attachment = VZFileHandleSerialPortAttachment(fileHandleForReading: FileHandle.standardInput, fileHandleForWriting: FileHandle.standardOutput)
config.serialPorts = [serial]
config.entropyDevices = [VZVirtioEntropyDeviceConfiguration()]
try config.validate()
let machine = VZVirtualMachine(configuration: config)
machine.start { result in
    switch result {
    case .success: print("ARTEL_VM_STARTED")
    case .failure(let error): print("ARTEL_VM_ERROR: \(error)"); exit(1)
    }
}
RunLoop.main.run()

```

## Транспорт vsock и оставшийся сетевой блокер

SSH через ProxyCommand nc -U control.sock успешно выполнил preflight UID1000. Swift launcher добавляет VZVirtioSocketDeviceConfiguration, control.sock chmod0600, connect guest port2222; гостевой socat VSOCK-LISTEN:2222,fork соединяет localhost:22. Команда: ssh -i vm/id_ed25519 -o IdentitiesOnly=yes -o UserKnownHostsFile=vm/known_hosts -o 'ProxyCommand=nc -U vm/control.sock' agent@stand-vsock python3 /work/preflight.py. Из двух swift-исходников собирается main.swift конкатенацией, затем swiftc -framework Virtualization main.swift -o run-vm-next и codesign с прежним entitlement.

route -n get 192.168.64.2 показал interface utun4/default. Привязанный к bridge100 диагностический сокет хоста также не подключился. У гостя DHCP/шлюз/DNS назначены, но gethostbyname завершился EAI_AGAIN, connect_ex к разрешённому хостом адресу registry.npmjs.org:443 завершился 11 после таймаута. Host VPN, маршруты и production-env/guards не изменялись. Предоставление сети VM либо другого Linux-хоста вынесено на решение Оператора; ANSWER-5 не снимает AC17.

Гостевой systemd unit stand-vsock-ssh.service: After=ssh.service; ExecStart=/usr/bin/socat VSOCK-LISTEN:2222,reuseaddr,fork TCP:127.0.0.1:22; Restart=on-failure; WantedBy=multi-user.target. Он подготовлен в собственном госте. Временный root autologin удалён; сетевой SSH по паролю/root запрещён. Учётных данных провайдеров в VM нет.

### vsock vm/vsock-relay.swift

```swift
import Foundation
import Virtualization
import Darwin

// Runs beside the launcher, uses only a local AF_UNIX control endpoint.
func relay(_ a: Int32, _ b: Int32) {
 for pair in [(a,b),(b,a)] {
  DispatchQueue.global().async {
   var buffer=[UInt8](repeating:0,count:65536)
   while true {
    let count=read(pair.0,&buffer,buffer.count)
    if count<=0 { shutdown(pair.1,SHUT_WR); break }
    var offset=0
    while offset<count {
     let sent=buffer.withUnsafeBytes { write(pair.1,$0.baseAddress!.advanced(by:offset),count-offset) }
     if sent<=0 { return }; offset += sent
    }
   }
  }
 }
}

```

### vsock vm/run-vm.swift

```swift
import Foundation
import Virtualization
import Darwin

let root = URL(fileURLWithPath: CommandLine.arguments[1])
let config = VZVirtualMachineConfiguration()
let boot = VZLinuxBootLoader(kernelURL: root.appendingPathComponent("vmlinuz"))
boot.initialRamdiskURL = root.appendingPathComponent("initrd.img")
boot.commandLine = "root=/dev/vda rw console=hvc0 net.ifnames=0" + (CommandLine.arguments.contains("--repair") ? " init=/bin/sh" : "")
config.bootLoader = boot
config.cpuCount = 2
config.memorySize = 2 * 1024 * 1024 * 1024
let attachment = try VZDiskImageStorageDeviceAttachment(url: root.appendingPathComponent("root.raw"), readOnly: false)
config.storageDevices = [VZVirtioBlockDeviceConfiguration(attachment: attachment)]
let network = VZVirtioNetworkDeviceConfiguration()
network.macAddress = VZMACAddress(string: "02:7a:17:00:00:17")!
network.attachment = VZNATNetworkDeviceAttachment()
config.networkDevices = [network]
let serial = VZVirtioConsoleDeviceSerialPortConfiguration()
serial.attachment = VZFileHandleSerialPortAttachment(fileHandleForReading: FileHandle.standardInput, fileHandleForWriting: FileHandle.standardOutput)
config.serialPorts = [serial]
config.socketDevices = [VZVirtioSocketDeviceConfiguration()]
config.entropyDevices = [VZVirtioEntropyDeviceConfiguration()]
try config.validate()
let machine = VZVirtualMachine(configuration: config)
machine.start { result in
    switch result {
    case .success: print("ARTEL_VM_STARTED")
    case .failure(let error): print("ARTEL_VM_ERROR: \(error)"); exit(1)
    }
}
let controlPath = root.appendingPathComponent("control.sock").path
unlink(controlPath)
let server = socket(AF_UNIX, SOCK_STREAM, 0)
var address = sockaddr_un()
address.sun_family = sa_family_t(AF_UNIX)
let pathBytes = controlPath.utf8CString
precondition(pathBytes.count < MemoryLayout.size(ofValue: address.sun_path))
withUnsafeMutableBytes(of: &address.sun_path) { destination in
 pathBytes.withUnsafeBytes { source in destination.copyBytes(from: source) }
}
let bound = withUnsafePointer(to: &address) { pointer in
 pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(server, $0, socklen_t(MemoryLayout<sockaddr_un>.size)) }
}
precondition(bound == 0)
chmod(controlPath, 0o600)
listen(server, 4)
DispatchQueue.global().async {
 while true {
  let client = accept(server, nil, nil)
  if client < 0 { break }
  DispatchQueue.main.async {
   let device = machine.socketDevices[0] as! VZVirtioSocketDevice
   device.connect(toPort: 2222) { result in
    switch result {
    case .success(let connection):
     let remote = dup(connection.fileDescriptor)
     relay(client,remote)
    case .failure(let error): print("VSOCK_CONNECT_ERROR: \(error)"); close(client)
    }
   }
  }
 }
}
RunLoop.main.run()

```

## Решение Оператора и сеть VM (15.10, 06:34 UTC)

Оператор разрешил настроить сеть только этой VM, сохранив VPN и запреты ролей. Подготовлены отдельные гостевые nftables table ip stand_transport, redsocks TCP→SOCKS и DNS UDP→локальный TCP relay. SSH через vsock несёт remote dynamic SOCKS 127.0.0.1:1080 и reverse 127.0.0.1:5353→host127.0.0.1:33553. Хостовый DNS relay слушает только loopback и использует обычный host getaddrinfo. Ни VPN, ни host routes, ни role-env/профили/guards не менялись. Корневой SSH-доступ гостя был временно открыт только по эфемерному ключу для установки пакетов и закрыт самим setup: PermitRootLogin no, ключ root удалён. Учётных данных провайдеров в VM нет.

Проверка от UID1000: HTTPS к https://registry.npmjs.org/@openai/codex/0.157.1 вернул HTTP200. Повторный preflight: native CLI версии прежние, unshare NEWUSER rc0, bwrap smoke rc0; внутри bwrap --unshare-all прямой TCP вернул101 (network unreachable). Это только проверка зависимостей/транспорта и отдельного сетевого запрета; не доказательство production-политики либо четырёх live-provider-маршрутов. ready_for_live остаётся false.

Восстановление сети после перезапуска VM требует поднять DNS relay и SSH remote forwards, затем заново применить гостевой отдельный nft table (таблица не записана в глобальный nftables.conf). Остановка сети: остановить эти два host-процесса; удалить только table ip stand_transport в госте, остановить stand-dns/stand-redsocks и восстановить systemd-resolved resolv.conf. Глобальный firewall не сбрасывается. Для SSH нужен предписанный own control.sock, эфемерный ключ и known_hosts.

### Сеть: vm/fetch-network-debs.py

```
import subprocess,uuid,json
from pathlib import Path
root=Path(__file__).resolve().parent
cid=None
def run(args,timeout=120):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 if p.returncode:raise RuntimeError((p.stderr or p.stdout)[-1500:])
 return p.stdout.strip()
try:
 cid=run(['docker','create','--user','root','--label','artel.operator.live-stand=true','--name','artel-vm-net-'+uuid.uuid4().hex[:8],'artel-live-stand:codex-0.157.1-claude-2.1.283','sleep','900'])
 run(['docker','start',cid]);run(['docker','exec',cid,'apt-get','-o','Acquire::Retries=0','-o','Acquire::https::Timeout=15','update'])
 run(['docker','exec',cid,'apt-get','--download-only','install','-y','nftables','redsocks'])
 dest=root/'network-debs';dest.mkdir(exist_ok=True)
 run(['docker','cp',cid+':/var/cache/apt/archives/.',str(dest)])
 print('network_debs_ready',flush=True)
finally:
 if cid:print('own_builder_removed='+str(subprocess.run(['docker','rm','-f',cid],capture_output=True,timeout=20).returncode==0),flush=True)

```

### Сеть: vm/dns-relay.py

```
"""Stand-only DNS over one loopback TCP stream per UDP query; host resolver."""
import socket,socketserver,struct
class Handler(socketserver.BaseRequestHandler):
 def handle(self):
  self.request.settimeout(5)
  try:
   data=self.request.recv(4096)
   if len(data)<12 or struct.unpack('!H',data[4:6])[0]!=1:return
   labels=[];at=12
   while at<len(data) and data[at]:
    size=data[at];at+=1
    if size>63 or at+size>len(data):return
    labels.append(data[at:at+size].decode('ascii'));at+=size
   at+=1
   if at+4>len(data):return
   kind,cls=struct.unpack('!HH',data[at:at+4]);question=data[12:at+4]
   answers=[];rcode=0
   if cls==1 and kind in (1,28):
    family=socket.AF_INET if kind==1 else socket.AF_INET6
    try:
     for ip in sorted({row[4][0] for row in socket.getaddrinfo('.'.join(labels),None,family,socket.SOCK_STREAM)}):
      packed=socket.inet_pton(family,ip)
      answers.append(b'\xc0\x0c'+struct.pack('!HHIH',kind,1,60,len(packed))+packed)
    except socket.gaierror:rcode=3
   result=data[:2]+struct.pack('!HHHHH',0x8180|rcode,1,len(answers),0,0)+question+b''.join(answers)
   self.request.sendall(result)
  except (OSError,ValueError,UnicodeError):return
class Server(socketserver.ThreadingTCPServer):
 allow_reuse_address=True;daemon_threads=True
with Server(('127.0.0.1',33553),Handler) as server:server.serve_forever()

```

### Сеть: vm/guest-network-setup.sh

```
set -eu
dpkg -i /work/network-debs/*.deb
cat > /etc/redsocks.conf <<'EOF'
base { log_debug=off; log_info=off; daemon=off; redirector=iptables; }
redsocks { local_ip=127.0.0.1; local_port=12345; ip=127.0.0.1; port=1080; type=socks5; }
EOF
cat > /etc/systemd/system/stand-redsocks.service <<'EOF'
[Service]
ExecStart=/usr/sbin/redsocks -c /etc/redsocks.conf
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/stand-dns.service <<'EOF'
[Service]
ExecStart=/usr/bin/socat UDP4-RECVFROM:53,bind=127.0.0.1,reuseaddr,fork TCP:127.0.0.1:5353
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now stand-redsocks stand-dns
# A separate table in this disposable guest only; no host or role namespace changes.
nft add table ip stand_transport
nft 'add chain ip stand_transport output { type nat hook output priority dstnat; policy accept; }'
nft add rule ip stand_transport output ip daddr 127.0.0.0/8 return
nft add rule ip stand_transport output ip protocol tcp redirect to :12345
rm -f /etc/resolv.conf
printf 'nameserver 127.0.0.1\noptions timeout:3 attempts:1\n' > /etc/resolv.conf
printf 'PermitRootLogin no\nPasswordAuthentication no\n' > /etc/ssh/sshd_config.d/stand.conf
rm -f /root/.ssh/authorized_keys
systemctl reload ssh
printf 'STAND_NETWORK_SETUP_OK\n'

```
