import subprocess

def run_command(cmd, capture_output=False, check=False, shell=False):
    if capture_output:
        result = subprocess.run(cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
        return result.stdout.strip()
    else:
        result = subprocess.run(cmd, shell=shell)
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd)
        return result.returncode
