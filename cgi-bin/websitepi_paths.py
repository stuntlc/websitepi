"""Runtime paths shared by website CGI scripts."""
import os


def log_directory(root):
    configured = os.environ.get("WEBSITEPI_LOG_DIR")
    if configured is None:
        return os.path.join(root, "logs")
    if not os.path.isabs(configured):
        raise ValueError("WEBSITEPI_LOG_DIR must be an absolute path")
    return configured
