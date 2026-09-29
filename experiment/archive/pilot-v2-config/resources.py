"""Windows working-set and NVML sampling without changing the search environment."""
import ctypes as C
from ctypes import wintypes as W
import os, statistics, threading, time

SIZE_T=C.c_size_t
class PROCESSENTRY32(C.Structure):
    _fields_=[('dwSize',W.DWORD),('cntUsage',W.DWORD),('th32ProcessID',W.DWORD),
      ('th32DefaultHeapID',SIZE_T),('th32ModuleID',W.DWORD),('cntThreads',W.DWORD),
      ('th32ParentProcessID',W.DWORD),('pcPriClassBase',W.LONG),('dwFlags',W.DWORD),('szExeFile',W.WCHAR*260)]
class MEMORY(C.Structure):
    _fields_=[('cb',W.DWORD),('PageFaultCount',W.DWORD)]+[(x,SIZE_T) for x in
      ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
       'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]
class GPUMEM(C.Structure):
    _fields_=[('total',C.c_ulonglong),('free',C.c_ulonglong),('used',C.c_ulonglong)]

kernel=C.WinDLL('kernel32',use_last_error=True)
kernel.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD]; kernel.CreateToolhelp32Snapshot.restype=W.HANDLE
kernel.Process32FirstW.argtypes=[W.HANDLE,C.POINTER(PROCESSENTRY32)]
kernel.Process32NextW.argtypes=[W.HANDLE,C.POINTER(PROCESSENTRY32)]
kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
kernel.CloseHandle.argtypes=[W.HANDLE]
psapi=C.WinDLL('psapi',use_last_error=True)
psapi.GetProcessMemoryInfo.argtypes=[W.HANDLE,C.POINTER(MEMORY),W.DWORD]

def process_tree(roots):
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot==C.c_void_p(-1).value:raise OSError(C.get_last_error(),'Process snapshot failed')
    rows={};entry=PROCESSENTRY32();entry.dwSize=C.sizeof(entry)
    try:
        ok=kernel.Process32FirstW(snapshot,C.byref(entry))
        while ok:
            rows[entry.th32ProcessID]={'parent':entry.th32ParentProcessID,'name':entry.szExeFile}
            ok=kernel.Process32NextW(snapshot,C.byref(entry))
    finally:kernel.CloseHandle(snapshot)
    selected=set(roots)
    while True:
        added={p for p,r in rows.items() if r['parent'] in selected}-selected
        if not added:break
        selected.update(added)
    return {p:rows[p] for p in sorted(selected) if p in rows}

def rss(pid):
    handle=kernel.OpenProcess(0x0400|0x0010,False,pid)
    if not handle:raise OSError(C.get_last_error(),f'Cannot inspect PID {pid}')
    data=MEMORY();data.cb=C.sizeof(data)
    try:
        if not psapi.GetProcessMemoryInfo(handle,C.byref(data),data.cb):raise OSError(C.get_last_error(),'RSS failed')
        return data.WorkingSetSize
    finally:kernel.CloseHandle(handle)

class Monitor:
    def __init__(self,pids,interval=.1):
        self.pids=sorted(set(pids));self.interval=interval;self.samples=[];self.errors=[]
        self.stop_event=threading.Event();self.phase='idle'
        self.nv=C.WinDLL(r'C:\Windows\System32\nvml.dll')
        self.check(self.nv.nvmlInit_v2())
        self.device=C.c_void_p();self.check(self.nv.nvmlDeviceGetHandleByIndex_v2(0,C.byref(self.device)))
        self.nv.nvmlDeviceGetMemoryInfo.argtypes=[C.c_void_p,C.POINTER(GPUMEM)]
    @staticmethod
    def check(result):
        if result!=0:raise RuntimeError(f'NVML error {result}')
    def sample(self):
        mem=GPUMEM();self.check(self.nv.nvmlDeviceGetMemoryInfo(self.device,C.byref(mem)))
        values={str(p):rss(p) for p in self.pids}
        self.samples.append({'monotonic':time.perf_counter(),'phase':self.phase,
          'rss_bytes':sum(values.values()),'rss_by_pid':values,'vram_bytes':mem.used})
    def loop(self):
        due=time.perf_counter()
        while not self.stop_event.is_set():
            try:self.sample()
            except Exception as exc:self.errors.append(type(exc).__name__+': '+str(exc))
            due+=self.interval
            self.stop_event.wait(max(0,due-time.perf_counter()))
    def start(self):
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    def stop(self):
        self.stop_event.set();self.thread.join();self.nv.nvmlShutdown()
        idle=[x for x in self.samples if x['phase']=='idle'];active=[x for x in self.samples if x['phase']=='request']
        gaps=[b['monotonic']-a['monotonic'] for a,b in zip(self.samples,self.samples[1:])]
        return {'pids':self.pids,'samples':self.samples,'errors':self.errors,
          'valid':bool(idle and active) and not self.errors,'sample_interval_ms':self.interval*1000,
          'max_actual_interval_ms':max(gaps,default=0)*1000,
          'idle_vram_bytes':statistics.median(x['vram_bytes'] for x in idle) if idle else None,
          'peak_vram_bytes':max((x['vram_bytes'] for x in active),default=None),
          'peak_rss_bytes':max((x['rss_bytes'] for x in active),default=None)}

def monitored_pids(server_pid,worker_pid,rag):
    # The runner's worker is explicitly excluded from LLM Only; no child is counted twice.
    model_processes=process_tree([server_pid]); roots=set(model_processes)|{os.getpid()}
    if rag:roots.update(process_tree([worker_pid]))
    if server_pid not in model_processes:raise RuntimeError('Ollama server PID is absent')
    return sorted(roots),model_processes
