"""SSH settings for legacy and restricted Pi 5 microphone access."""
import os


HOST = "10.0.0.50"


def restricted():
    return os.environ.get("BTMIC_RESTRICTED") == "1"


def ssh_command(remote_command):
    user = os.environ.get("BTMIC_SSH_USER", os.environ.get("WEBSSH_USER", "q"))
    command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]
    if restricted():
        key = os.environ.get("BTMIC_SSH_KEY", "")
        if not os.path.isabs(key):
            raise ValueError("Restricted Bluetooth SSH key is not configured")
        command.extend(["-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes", "-i", key])
    return command + [user + "@" + HOST, remote_command]
