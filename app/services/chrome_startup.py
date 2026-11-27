import asyncio
import ipaddress
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen


LOGGER = logging.getLogger(__name__)


class ChromeStartup:
    def __init__(
        self,
        cdp_url: str,
        user_data_dir: Path,
        startup_urls: list[str],
        executable: str = "",
        auto_launch: bool = True,
        probe: Callable[[], bool] | None = None,
    ):
        self.cdp_url = cdp_url.rstrip("/")
        parsed_cdp_url = urlparse(self.cdp_url)
        if (
            parsed_cdp_url.scheme != "http"
            or not parsed_cdp_url.hostname
            or not self._is_loopback(parsed_cdp_url.hostname)
            or not parsed_cdp_url.port
        ):
            raise ValueError("CHROME_CDP_URL debe ser HTTP en loopback e incluir un puerto")
        self.user_data_dir = user_data_dir
        self.startup_urls = startup_urls
        self.executable = executable
        self.auto_launch = auto_launch
        self._probe = probe or self._cdp_is_available

    async def ensure_running(self) -> bool:
        if not self.auto_launch:
            return False
        if await asyncio.to_thread(self._probe):
            LOGGER.info("Chrome CDP ya esta disponible; no se iniciara otra instancia")
            return False

        executable = self._find_executable()
        if not executable:
            raise RuntimeError(
                "No se encontro Google Chrome. Configure CHROME_EXECUTABLE o desactive CHROME_AUTO_LAUNCH."
            )
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        command = self.build_command(executable)
        LOGGER.info("Iniciando Chrome dedicado con las paginas configuradas")
        subprocess.Popen(
            command,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        )

        for _ in range(30):
            await asyncio.sleep(0.5)
            if await asyncio.to_thread(self._probe):
                LOGGER.info("Chrome CDP esta disponible")
                return True
        raise RuntimeError(
            "Chrome se inicio, pero CDP no respondio en 15 segundos. "
            "Verifique el perfil dedicado, el puerto y que no exista otro proceso usando ese perfil."
        )

    def build_command(self, executable: str | Path) -> list[str]:
        parsed = urlparse(self.cdp_url)
        if not parsed.port:
            raise ValueError("CHROME_CDP_URL debe incluir el puerto CDP")
        return [
            str(executable),
            "--remote-debugging-address=127.0.0.1",
            f"--remote-debugging-port={parsed.port}",
            "--start-fullscreen",
            f"--user-data-dir={self.user_data_dir.resolve()}",
            *self.startup_urls,
        ]

    def _find_executable(self) -> str | None:
        if self.executable:
            path = Path(self.executable)
            if path.is_file():
                return str(path)
            return None

        candidates = [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
            / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
            / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Google/Chrome/Application/chrome.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return shutil.which("chrome") or shutil.which("chrome.exe")

    def _cdp_is_available(self) -> bool:
        try:
            with urlopen(f"{self.cdp_url}/json/version", timeout=1):
                return True
        except (URLError, TimeoutError, OSError):
            return False

    @staticmethod
    def _is_loopback(host: str) -> bool:
        if host.lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False
