"""MirageStorageBackend — write ai-crawler output through a Mirage Workspace.

All data written through this backend lands in the Mirage VFS at the configured
mount prefix.  If the Workspace has external resources mounted (S3, GDrive, …)
the data flows transparently to those services.

Usage::

    from mirage import Workspace, MountMode
    from mirage.resource.ram import RAMResource
    from mirage.resource.s3 import S3Resource, S3Config
    from ai_crawler.storage.mirage import MirageStorageBackend

    ws = Workspace(
        {"/output": RAMResource(),
         "/s3":    S3Resource(S3Config(bucket="my-bucket"))},
        mode=MountMode.WRITE,
    )
    backend = MirageStorageBackend(ws, mount_prefix="/s3/crawls")

    backend.makedirs("output")
    backend.write_text("output/results.jsonl", '{"title": "..."}\\n')
"""

from __future__ import annotations

import asyncio


class MirageStorageBackend:
    """StorageBackend that writes through a Mirage Workspace."""

    def __init__(self, workspace, mount_prefix: str = "/output"):
        self._ws = workspace
        self._mount = mount_prefix

    def _to_ws_path(self, path: str) -> str:
        return f"{self._mount}/{path}"

    def makedirs(self, path: str) -> None:
        ws_path = self._to_ws_path(path)
        # Ensure every parent directory exists up to the mount point
        parts = ws_path.split("/")
        for i in range(2, len(parts)):
            ancestor = "/".join(parts[:i])
            if ancestor == self._mount:
                continue
            try:
                asyncio.run(self._ws.ops.mkdir(ancestor))
            except Exception:
                pass

    def write_text(self, path: str, content: str) -> None:
        ws_path = self._to_ws_path(path)
        self.makedirs(path)
        asyncio.run(self._ws.ops.write(ws_path, content.encode("utf-8")))

    def append_text(self, path: str, content: str) -> None:
        ws_path = self._to_ws_path(path)
        self.makedirs(path)
        asyncio.run(self._ws.ops.append(ws_path, content.encode("utf-8")))

    def read_text(self, path: str) -> str:
        ws_path = self._to_ws_path(path)
        data = asyncio.run(self._ws.ops.read(ws_path))
        return data.decode("utf-8")

    def exists(self, path: str) -> bool:
        ws_path = self._to_ws_path(path)
        try:
            asyncio.run(self._ws.ops.stat(ws_path))
            return True
        except Exception:
            return False


def create_mirage_backend(
    output_dir: str = "/output",
    traces_dir: str = "/traces",
    memory_dir: str = "/memory",
    *,
    resources: dict | None = None,
) -> tuple[MirageStorageBackend, MirageStorageBackend, MirageStorageBackend]:
    """Create three MirageStorageBackend instances sharing one Workspace.

    Each backend writes to a separate mount point so output, traces, and memory
    stay in different directories.

    *resources* is an optional dict of Mirage resource mounts (e.g.
    ``{"/s3": S3Resource(...)}``).  If omitted the Workspace only has
    RAM-backed mounts.
    """
    from mirage import MountMode, Workspace
    from mirage.resource.ram import RAMResource

    mounts: dict = {
        output_dir: RAMResource(),
        traces_dir: RAMResource(),
        memory_dir: RAMResource(),
    }
    if resources:
        mounts.update(resources)

    ws = Workspace(mounts, mode=MountMode.WRITE)
    return (
        MirageStorageBackend(ws, mount_prefix=output_dir),
        MirageStorageBackend(ws, mount_prefix=traces_dir),
        MirageStorageBackend(ws, mount_prefix=memory_dir),
    )
