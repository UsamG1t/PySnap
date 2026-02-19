import sys
import pathlib
import atexit
import re

from ..common import VBM, log
from ..vbscan import VBScan

vm_format = lambda vm: f'''{vm['name']} ({vm["uart"]}):
''' + '\n'.join(f"\t{i}: {iname}" for i, iname in vm.get("networks", {"No Networks": ""}).items())

def usage():
    usage_text = f'''
    vbsnap — Creation and management of virtual machines

    Usage:
    vbsnap.py
    vbsnap.py list
    vbsnap.py [<image>.ova | <image>.ovf]
    vbsnap.py <VM>
    vbsnap.py <BaseVM> <CloneVM>[:<Port>] [<eth1-net> [<eth2-net> [<eth3-net>]]]
    vbsnap.py erase [--all | <CloneVM>]
    
    vbsnap.py --cli — Activate CLI interface 
        use cmds without filename
        use \'help\' for showing this message
        use \'quit\' or Ctrl+D for quit
    '''

    print(usage_text, file=sys.stderr)

vbscan = VBScan("/LinuxNetwork")

def parser(parse_blocks: list[str], **kwargs) -> bool:
    match parse_blocks:
        case []:
            usage()
        
        case ["list"]:
            for vm in vbscan.json_data["machines"]:
                print(vm_format(vm))
        
        case [image] if image.endswith(('.ova', '.ovf')):
            image_path = pathlib.Path(image).expanduser()
            image_name = image_path.parts[-1][:-4]

            if image_name.startswith('protocols') and \
                    any('protocols' in vm_name for vm_name in vbscan["names"]):
                log("This appliance already exists")
                return

            log('Importing appliance')
            VBM(['import', str(image_path)], debug=True)
            vbscan.scan()
        
        case [vm_name] if vm_name in vbscan["names"]:
            vm_idx = vbscan[vm_name]
            print(vm_format(vbscan["machines"][vm_idx]))
        
        case [BaseVM, CloneVM, *networks_names] if BaseVM in vbscan["names"]:
            if ':' in CloneVM:
                CloneName, ClonePort = CloneVM.split(':')
            else:
                CloneName, ClonePort = CloneVM, vbscan["new_uart"]
            
            base_snap = vbscan["machines"][vbscan[BaseVM]].get("snapshots")
            if base_snap is None:
                VBM(["snapshot", BaseVM, "take", BaseVM + "_vbsnap"], debug=True)

                result = VBM(['showvminfo', BaseVM], no_print=True)
                vbscan.update_VMs_from_text(result.stdout)

            base_snap = vbscan["machines"][vbscan[BaseVM]].get("snapshots")[0]

            VBM_args = ["clonevm", BaseVM, 
                        f"--groups={vbscan["group"]}", 
                        f"--name={CloneName}", 
                        "--options=Link", 
                        "--register", 
                        "--snapshot", base_snap]
            VBM(VBM_args, debug=True)

            Nets = []
            for net_idx, network_name in enumerate(networks_names, start=2):
                Nets += [f"--nic{net_idx}", "intnet", 
                         f"--intnet{net_idx}", network_name, 
                         f"--cableconnected{net_idx}", "on"]

            VBM_args = ["modifyvm", CloneName, 
                        "--uartmode1", "tcpserver", str(ClonePort)]
            VBM_args += Nets
            VBM(VBM_args, debug=True)

            VBM_args = ["setextradata", CloneName, 
                        "VBoxInternal/Devices/pcbios/0/Config/DmiSystemVendor", 
                        CloneName.upper()]
            VBM(VBM_args, debug=True)

            sku = f"port{ClonePort}." + '.'.join(networks_names)
            VBM_args = ["setextradata", 
                        CloneName, 
                        "VBoxInternal/Devices/pcbios/0/Config/DmiSystemSKU", 
                        sku]
            VBM(VBM_args, debug=True)
            
            result = VBM(['showvminfo', CloneName], no_print=True)
            vbscan.update_VMs_from_text(result.stdout)
        
        case ["erase", vm_name] if vm_name in vbscan["names"]:
            vm_idx = vbscan[vm_name]
            vm_info = vbscan["machines"][vm_idx]

            if vm_info.get("snapshots") is not None:
                for snap in vm_info["snapshots"]:
                    VBM(["snapshot", vm_info["name"], "delete", snap], debug=True)
            
            VBM(["unregistervm", "--delete", vm_info["name"]], debug=True)
        
            vbscan.delVM(vm_name)

        case ["erase", "--all"]:
            for vm in reversed(vbscan["machines"]):
                parser(["erase", vm["name"]])

        case _:
            log("Undefined command", f"«{' '.join(parse_blocks)}»")
            usage()

def starter():
    if '--cli' in sys.argv:
        while True:
            try:
                args = input('vbsnap>> ')
            except EOFError:
                break
            
            if args == 'help':
                parser([])
            elif args == 'quit':
                break
            elif args != '':
                parser(args.split())
    else:
        parser(sys.argv[1:])

@atexit.register
def final_dump():
    vbscan.dump()

if __name__ == "__main__":
    starter()