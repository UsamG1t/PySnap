import json
import pathlib
import re

from ..common import log, VBM

class VBScan:

    def __init__(self, group: str, db: str = '~/.vbscan'):
        self.db_path = pathlib.Path(db).expanduser()
        self.db_path.touch()

        with open(self.db_path, 'r') as dbf:
            try:
                self.json_data = json.load(dbf)
            except json.decoder.JSONDecodeError:
                self.json_data = {
                    "group": group,
                    "machines": []
                }

        self.scan()

    def __str__(self):
        return json.dumps(self.json_data)
    
    def __getitem__(self, item: str):
        match item:
            case "group" | "machines" as var:
                return self.json_data[var]
            case "new_uart":
                return max(vm["uart"] for vm in self["machines"]) + 1
            case "names":
                return [vm["name"] for vm in self["machines"]]
            case vm_name if vm_name in self["names"]:
                try:
                    return self["names"].index(vm_name)
                except ValueError:
                    return None
            case _:
                return None
    
    def addVM(self, vm: dict[str, str | int | dict[str, str]]):
        idx = self[vm['name']]
        if idx is not None:
            self.json_data["machines"][idx] = vm
        else:
            self.json_data["machines"].append(vm)

    def delVM(self, name: str):
        idx = self[name]
        del self.json_data["machines"][idx]

    def dump(self):
        with open(self.db_path, 'w+') as dbf:
            json.dump(self.json_data, dbf, indent=4)
            log(f"Dump VMs info in {self.db_path}")

    def update_VMs_from_text(self, text: str):
        json_item = None

        for line in text.split('\n'):
            if line.startswith('Name') and not line.strip().endswith('*'):
                '''vm name'''
                
                if json_item and self["group"] in json_item["group"]:
                    self.addVM(json_item)
                
                json_item = {}
                name = line.split()[-1]
                json_item.update({"name": name})
            
            elif line.lstrip().startswith('Name') and line.strip().endswith('*'):
                '''vm snapshots'''
                snapshot = line.split()[1]
                
                if json_item.get("snapshots", None) is None:
                    json_item.update({"snapshots": []})

                json_item["snapshots"].append(snapshot)
                
            
            elif line.startswith('Groups'):
                '''vm group'''
                group = line.split()[-1]
                json_item.update({"group": group})
            
            elif line.startswith('UART 1'):
                '''vm UART'''
                uart_ptn = r"'(\d+)'"
                uart = int(re.search(uart_ptn, line).group(1))
                json_item.update({"uart": uart})

            elif 'Internal Network' in line:
                '''vm network interfaces'''
                uart_ptn = r"'(.+)'"
                network = re.search(uart_ptn, line).group(1)
                
                if json_item.get("networks") is None:
                    json_item.update({"networks": {}})
                
                json_item["networks"].update({f"eth{int(line[4])-1}": network})

        if json_item and self["group"] in json_item["group"]:
            self.addVM(json_item)
        

    def scan(self):
        result = VBM(['list', '--long', 'vms'], no_print=True)
        if result.returncode != 0:
            log("Scan error")
            return None

        self.update_VMs_from_text(result.stdout)
        self.dump()
        
        return self.json_data
        
    