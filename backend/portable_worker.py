"""A bounded subprocess contains blocking platform HID calls. RGB actions only."""
import json,sys
from hid_transport import PortableHID
def main():
    try:
        raw=sys.stdin.buffer.read(8193)
        if len(raw)>8192:raise ValueError('Colour request too large.')
        body=json.loads(raw)
        if set(body)!={'action','payload','device_id'}:raise ValueError('Invalid typed request.')
        result=PortableHID().command(body['action'],body['payload'],body['device_id'])
    except (ValueError,TypeError,KeyError) as e:result={'ok':False,'error':str(e),'submitted_count':0,'accepted_count':0}
    print(json.dumps(result));return 0 if result.get('ok') else 1
if __name__=='__main__':raise SystemExit(main())
