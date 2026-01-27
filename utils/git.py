"""CLI 공통 유틸리티"""

import subprocess


def get_git_user_email() -> str | None:
    """git config에서 user.email 가져오기"""
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
