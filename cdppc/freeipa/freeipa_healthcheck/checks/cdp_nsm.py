from utils.shell import run_command
from utils.colors import GREEN, RED, NC

def freeipa_cdp_nsm():
    ret = run_command(["systemctl", "is-active", "cdp-node-status-monitor"], capture_output=True)
    if ret == "active":
        print(f"{GREEN}CDP Node Status Monitor service is running.{NC}")
    else:
        print(f"{RED}CDP Node Status Monitor service is NOT running.{NC}")
