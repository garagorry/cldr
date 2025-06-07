from utils.shell import run_command
from utils.colors import GREEN, RED, NC

def freeipa_status():
    ret = run_command(["ipa", "healthcheck"], capture_output=True)
    if "ERROR" in ret or "FAILED" in ret:
        print(f"{RED}FreeIPA healthcheck reports errors!{NC}")
        print(ret)
    else:
        print(f"{GREEN}FreeIPA healthcheck OK.{NC}")
