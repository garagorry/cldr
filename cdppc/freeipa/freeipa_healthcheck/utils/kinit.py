import subprocess
import os

def kinit_authenticate():
    PRINCIPAL = os.getenv("FREEIPA_PRINCIPAL")
    PASSWORD = os.getenv("FREEIPA_PASSWORD")
    if not PRINCIPAL or not PASSWORD:
        print("Kerberos principal or password not set in environment variables.")
        return False
    try:
        proc = subprocess.run(['kinit', PRINCIPAL], input=PASSWORD+'\n', text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode == 0
    except Exception as e:
        print(f"kinit failed: {e}")
        return False
