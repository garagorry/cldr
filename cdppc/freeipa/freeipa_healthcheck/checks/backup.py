from utils.shell import run_command
from utils.colors import GREEN, RED, NC

def freeipa_test_backup():
    backup_path = "/var/lib/ipa/backup"
    ret = run_command(["ls", "-l", backup_path], capture_output=True)
    if ret:
        print(f"{GREEN}Backup directory {backup_path} exists and has files.{NC}")
    else:
        print(f"{RED}Backup directory {backup_path} missing or empty.{NC}")
