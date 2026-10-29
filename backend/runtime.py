"""Read-only bundled resources and writable per-user state, kept separate."""
from pathlib import Path
import os,sys
FROZEN=bool(getattr(sys,'frozen',False))
ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
VERSION='0.3.0-experimental'
def data_root():
    if not FROZEN:return ROOT/'data'
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/Ducky Lighting'
    if sys.platform=='win32':return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'Ducky Lighting'
    xdg=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))
    return (xdg if xdg.is_absolute() else Path.home()/'.local/share')/'ducky-lighting'
