"""Build the documented desktop candidate and privacy-audited public archives."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

if __name__ == '__main__':
    subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass',
                    '-File',str(ROOT/'tools/build_plugins.ps1')],check=True,cwd=ROOT)
    name = 'CS2Career-150-rc-20260910-4'
    subprocess.run([sys.executable,'build_desktop_preview.py','--integration','--name',name],check=True,cwd=ROOT)
    subprocess.run([sys.executable,'tools/package_public.py','--exe',
                    str(ROOT/'release'/name/(name+'.exe'))],check=True,cwd=ROOT)
