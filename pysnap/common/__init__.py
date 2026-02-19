import subprocess
import sys
import os

arge = os.environ.copy()
arge['LC_ALL'] = 'en_US.UTF-8'

def log(message: str, special_info: str = None):
    """Execution info: logs, errors, messages"""
    print(message, file=sys.stderr)
    
    if special_info is not None:
        print(special_info, file=sys.stderr)


def VBM(args: list[str], **kwargs):
    
    if kwargs.get('debug'):
        log(f"# VBoxManage {' '.join(args)}")

    result = subprocess.run(
        ['VBoxManage'] + args,
        capture_output=True,
        encoding='utf-8', 
        text=True, 
        env=arge
    )

    if kwargs.get("no_print") is not True:
        print(result.stdout)  
    
    if result.returncode != 0:
        log('Error during execution of VBoxManage:', result.stderr)
    
    return result
