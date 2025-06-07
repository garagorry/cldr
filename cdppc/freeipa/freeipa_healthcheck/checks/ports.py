from utils.shell import run_command
from utils.colors import GREEN, RED, NC

REQUIRED_PORTS = [80, 443, 389, 636, 88, 464]

def freeipa_checkports():
    ret = run_command(["ss", "-tuln"], capture_output=True)
    for port in REQUIRED_PORTS:
        if f":{port} " in ret:
            print(f"{GREEN}Port {port} is LISTENING{NC}")
        else:
            print(f"{RED}Port {port} is NOT listening{NC}")
