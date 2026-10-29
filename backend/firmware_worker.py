"""Console helper for packaged Windows/Linux: fixed-image firmware only, or typed RGB.
The worker never reopens a HID handle after inspection. A stale path cannot redirect a plan.
"""
import json,queue,sys,threading
from firmware_hid import LoaderSession,pinned_image

def send(event):print(json.dumps(event),flush=True)
def read():
    line=sys.stdin.readline(4097)
    if not line or len(line)>4096:raise ValueError('Firmware request ended or was too large.')
    body=json.loads(line)
    if not isinstance(body,dict):raise ValueError('Invalid firmware request.')
    return body

def self_test():
    from firmware_virtual import verify
    import hid  # Load the bundled native library; do not enumerate or open devices.
    result=verify();result['hid_library_imported']=True
    send(result);return 0

def main():
    if sys.argv[1:]==['--rgb']:
        from portable_worker import main as rgb
        return rgb()
    if sys.argv[1:]==['--self-test']:return self_test()
    if sys.argv[1:]:raise ValueError('Unsupported worker option.')
    session=None
    try:
        body=read()
        if set(body)!={'action','device_id'} or body['action']!='inspect' or not isinstance(body['device_id'],str):raise ValueError('Invalid inspection request.')
        events=[];session=LoaderSession(body['device_id'],emit=events.append)
        session.execute(bytes(65000),True);send({'event':'ready','events':events})
        # No HID writes while waiting. Expiry or closed stdin releases this same handle.
        replies=queue.Queue()
        def approval():
            try:replies.put(read())
            except Exception as error:replies.put(error)
        threading.Thread(target=approval,daemon=True).start()
        try:body=replies.get(timeout=120)
        except queue.Empty:raise ValueError('Firmware confirmation expired. No erase sent.')
        if isinstance(body,Exception):raise body
        if set(body)!={'action','image','image_path'} or body['action']!='program' or not isinstance(body['image_path'],str):raise ValueError('Invalid programming request.')
        image=pinned_image(body['image_path'],body['image'])
        session.emit=send;session.execute(image);return 0
    except Exception as error:
        send({'event':'failure','error':str(error),'aprom_attempted':bool(session and session.aprom_attempted)});return 1
    finally:
        if session:session.close()
if __name__=='__main__':raise SystemExit(main())
