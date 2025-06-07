from utils.shell import run_command
from utils.colors import GREEN, RED, NC

def freeipa_check_saltuser_password_rotation():
    ret = run_command(["salt", "*", "pillar.get", "freeipa:saltuser_password_rotation"], capture_output=True)
    if "True" in ret:
        print(f"{GREEN}Salt user password rotation enabled.{NC}")
    else:
        print(f"{RED}Salt user password rotation not enabled or could not detect.{NC}")

def freeipa_ccm_network_status():
    ret = run_command(["ping", "-c", "3", "ccm.example.com"], capture_output=True)
    if "0% packet loss" in ret:
        print(f"{GREEN}Control Plane network status OK.{NC}")
    else:
        print(f"{RED}Control Plane network status FAIL.{NC}")

def freeipa_ccm():
    ret = run_command(["systemctl", "is-active", "ccm"], capture_output=True)
    if ret == "active":
        print(f"{GREEN}CCM service is running.{NC}")
    else:
        print(f"{RED}CCM service is NOT running.{NC}")
