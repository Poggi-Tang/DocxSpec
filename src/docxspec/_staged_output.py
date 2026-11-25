"""Publish a generated artifact only after its processing succeeds."""

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory


@contextmanager
def staged_output(destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".docxspec-", dir=destination.parent) as folder:
        staged = Path(folder) / destination.name
        yield staged
        staged.replace(destination)
