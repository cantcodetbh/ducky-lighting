"""Reproduce pinned firmware images from a local official updater; never executes it or opens USB."""
from pathlib import Path
import argparse,sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from firmware import construct_images,digest
p=argparse.ArgumentParser(description=__doc__);p.add_argument('updater',type=Path);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
images=construct_images(args.updater.read_bytes());args.out.mkdir(parents=True,exist_ok=True)
for name,data in images.items():
    (args.out/(name+'.bin')).write_bytes(data)
    print(json.dumps({'image':name,'length':len(data),'sha256':digest(data),'USB_calls':0}))
