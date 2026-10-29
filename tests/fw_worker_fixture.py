"""Test-process entry only. No production code imports this or accepts an injected HID module."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import firmware_hid,firmware_worker
from firmware_virtual import VirtualHID
fake=VirtualHID()
firmware_hid.library=lambda:fake
firmware_worker.pinned_image=lambda path,name:bytes(i%251 for i in range(65000 if name=='candidate' else 63848))
raise SystemExit(firmware_worker.main())
