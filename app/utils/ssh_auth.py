"""
SSH authentication helpers.
"""
import shutil
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Dict, Optional

import paramiko


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_credential_path(reference: str) -> Optional[Path]:
    """Resolve a credential reference to an existing file path."""
    raw_path = Path(reference).expanduser()

    candidates = [
        raw_path,
        Path.cwd() / raw_path,
        PROJECT_ROOT / raw_path,
        PROJECT_ROOT / "app" / raw_path,
    ]

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue

    return None


def _load_private_key(key_path: Path):
    """Load a private key file using Paramiko's supported loaders."""
    loader_errors = []

    if hasattr(paramiko.PKey, "from_path"):
        try:
            return paramiko.PKey.from_path(str(key_path))
        except Exception as exc:
            loader_errors.append(str(exc))

    from paramiko import DSSKey, ECDSAKey, Ed25519Key, RSAKey

    for key_class in (RSAKey, Ed25519Key, ECDSAKey, DSSKey):
        try:
            return key_class.from_private_key_file(str(key_path))
        except Exception as exc:
            loader_errors.append(f"{key_class.__name__}: {exc}")

    raise ValueError("; ".join(loader_errors) if loader_errors else "Unable to load private key")


def _convert_ppk_to_openssh(key_path: Path):
    """Convert a PuTTY PPK private key to a temporary OpenSSH private key."""
    puttygen_path = shutil.which("puttygen")
    if not puttygen_path:
        raise ValueError("puttygen is not installed or not available on PATH")

    temp_key_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as temp_file:
            temp_key_path = Path(temp_file.name)

        subprocess.run(
            [
                puttygen_path,
                str(key_path),
                "-O",
                "private-openssh",
                "-o",
                str(temp_key_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        try:
            return _load_private_key(temp_key_path)
        finally:
            with suppress(Exception):
                temp_key_path.unlink(missing_ok=True)
    except subprocess.CalledProcessError as exc:
        if temp_key_path:
            with suppress(Exception):
                temp_key_path.unlink(missing_ok=True)
        error_output = (exc.stderr or exc.stdout or str(exc)).strip()
        raise ValueError(f"puttygen failed to convert PPK key: {error_output}") from exc
    except Exception:
        if temp_key_path:
            with suppress(Exception):
                temp_key_path.unlink(missing_ok=True)
        raise


def build_ssh_connect_kwargs(
    hostname: str,
    username: str,
    credential_reference: Optional[str],
    *,
    port: int = 22,
    timeout: int = 30,
    banner_timeout: Optional[int] = None,
    auth_timeout: Optional[int] = None,
) -> Dict[str, object]:
    """Build Paramiko connect kwargs from either a password or a key file."""
    connect_kwargs: Dict[str, object] = {
        "hostname": hostname,
        "port": port,
        "username": username,
        "timeout": timeout,
        "look_for_keys": False,
        "allow_agent": False,
    }

    if banner_timeout is not None:
        connect_kwargs["banner_timeout"] = banner_timeout

    if auth_timeout is not None:
        connect_kwargs["auth_timeout"] = auth_timeout

    if not credential_reference:
        return connect_kwargs

    credential_path = _resolve_credential_path(credential_reference)
    if credential_path:
        try:
            if credential_path.suffix.lower() == ".ppk":
                connect_kwargs["pkey"] = _convert_ppk_to_openssh(credential_path)
                return connect_kwargs

            connect_kwargs["pkey"] = _load_private_key(credential_path)
            return connect_kwargs
        except Exception as exc:
            raise ValueError(
                f"Unable to load SSH private key from {credential_path}: {exc}"
            ) from exc

    connect_kwargs["password"] = credential_reference
    return connect_kwargs