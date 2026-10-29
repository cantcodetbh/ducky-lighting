"""An isolated worker retains one HID handle between inspection and confirmed programming."""
import json,os,queue,subprocess,sys,threading
from pathlib import Path
from runtime import ROOT,FROZEN

def worker_command():
    if FROZEN:return [str(Path(sys.executable).parent/('DuckyFirmwareWorker.exe' if sys.platform=='win32' else 'DuckyFirmwareWorker'))]
    return [sys.executable,str(ROOT/'backend/firmware_worker.py')]

class SessionProcess:
    def __init__(self,device_id):
        options={'creationflags':subprocess.CREATE_NO_WINDOW} if sys.platform=='win32' else {}
        self.process=subprocess.Popen(worker_command(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1,**options)
        self.queue=queue.Queue(maxsize=4096)
        self.reader=threading.Thread(target=self._read,daemon=True);self.reader.start()
        self.send({'action':'inspect','device_id':device_id})
    def _read(self):
        try:
            while True:
                line=self.process.stdout.readline(20001)
                if not line:break
                if len(line)>20000:raise ValueError('Invalid worker response.')
                self.queue.put(json.loads(line))
        except (OSError,ValueError) as error:self.queue.put({'event':'failure','error':str(error)})
        finally:self.queue.put(None)
    def send(self,body):
        if self.process.poll() is not None:raise ValueError('Bootloader session expired. Check the connection again.')
        self.process.stdin.write(json.dumps(body)+'\n');self.process.stdin.flush()
    def receive(self,timeout):
        try:event=self.queue.get(timeout=timeout)
        except queue.Empty:raise ValueError('Bootloader worker timed out. No retry sent.')
        if event is None:raise ValueError('Bootloader session ended. No retry sent.')
        if event.get('event')=='failure':raise ValueError(event.get('error','Bootloader operation failed.'))
        return event
    def inspect(self):
        event=self.receive(15)
        if event.get('event')!='ready':raise ValueError('Invalid bootloader inspection response.')
        return event['events']
    def program(self,name,path):
        self.send({'action':'program','image':name,'image_path':str(path)})
        while True:
            event=self.receive(40)
            yield event
            if event.get('event')=='program_result':
                self.process.wait(timeout=5)
                if self.process.returncode:raise ValueError('Bootloader worker failed after its result.')
                return
    def close(self):
        try:self.process.stdin.close()
        except (OSError,ValueError):pass
        try:self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:self.process.terminate();self.process.wait(timeout=5)
            except (OSError,subprocess.TimeoutExpired):pass
        if self.process.poll() is not None:
            self.reader.join(timeout=2)
            try:self.process.stdout.close()
            except OSError:pass

