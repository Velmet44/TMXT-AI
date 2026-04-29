from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


class NgrokManager:
    def __init__(
        self,
        *,
        enabled: bool,
        app_port: int,
        executable_path: str | None,
        authtoken: str | None,
        api_base_url: str,
        url: str | None,
    ) -> None:
        self.enabled = enabled
        self.app_port = app_port
        self.executable_path = executable_path
        self.authtoken = authtoken
        self.api_base_url = api_base_url.rstrip("/")
        self.url = url
        self._process: subprocess.Popen[str] | None = None
        self.public_url: str | None = None

    def start(self) -> str | None:
        if not self.enabled:
            return None

        executable = self._resolve_executable()
        if executable is None:
            print("ngrok autostart enabled, but ngrok.exe was not found. Coordinator will continue without a tunnel.")
            return None

        command = [executable, "http", str(self.app_port)]
        if self.authtoken:
            command.extend(["--authtoken", self.authtoken])
        if self.url:
            command.extend(["--url", self.url])

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        self._process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            text=True,
            creationflags=creationflags,
        )
        atexit.register(self.stop)

        self.public_url = self._wait_for_public_url()
        if self.public_url:
            print(f"ngrok public URL: {self.public_url}")
            print(f"Worker endpoint: {self.public_url.replace('https://', 'wss://').replace('http://', 'ws://')}/ws/worker")
            print(f"Client endpoint: {self.public_url.replace('https://', 'wss://').replace('http://', 'ws://')}/ws/client")
        return self.public_url

    def stop(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    def _resolve_executable(self) -> str | None:
        candidates: list[Path] = []
        if self.executable_path:
            candidates.append(Path(self.executable_path))

        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().with_name("ngrok.exe"))
        else:
            candidates.append(Path(__file__).resolve().parents[2] / "ngrok.exe")

        for candidate in candidates:
            if candidate.exists():
                return str(candidate.resolve())

        return self._which("ngrok.exe") or self._which("ngrok")

    @staticmethod
    def _which(name: str) -> str | None:
        for entry in os.environ.get("PATH", "").split(os.pathsep):
            candidate = Path(entry) / name
            if candidate.exists():
                return str(candidate)
        return None

    def _wait_for_public_url(self) -> str | None:
        deadline = time.time() + 30
        tunnels_url = f"{self.api_base_url}/tunnels"
        while time.time() < deadline:
            if self._process is not None and self._process.poll() is not None:
                print("ngrok exited before exposing a public URL.")
                return None

            try:
                with urlopen(tunnels_url, timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                public_url = self._extract_public_url(payload)
                if public_url:
                    return public_url
            except (URLError, TimeoutError, json.JSONDecodeError, OSError):
                pass
            time.sleep(0.5)
        print("ngrok started, but no public URL was detected from the local agent API.")
        return None

    @staticmethod
    def _extract_public_url(payload: dict[str, Any]) -> str | None:
        tunnels = payload.get("tunnels", [])
        https_url = None
        for tunnel in tunnels:
            public_url = tunnel.get("public_url")
            if not isinstance(public_url, str):
                continue
            if public_url.startswith("https://"):
                https_url = public_url
                break
            if public_url.startswith("http://") and https_url is None:
                https_url = public_url
        return https_url
