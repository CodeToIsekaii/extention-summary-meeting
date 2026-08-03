from pathlib import Path
from subprocess import run

import imageio_ffmpeg
import pytest

from meet_assistant.audio import LocalAudioFinalizer


def _make_webm(path: Path, frequency: int) -> None:
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    result = run(
        [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:duration=0.2",
            "-c:a",
            "libopus",
            "-y",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_finalize_mixes_remote_and_microphone_tracks(tmp_path: Path) -> None:
    session = tmp_path / "session"
    remote = session / "chunks" / "remote"
    microphone = session / "chunks" / "me"
    remote.mkdir(parents=True)
    microphone.mkdir(parents=True)
    _make_webm(remote / "00000000.webm", 440)
    _make_webm(microphone / "00000000.webm", 660)
    output = tmp_path / "recording.webm"

    LocalAudioFinalizer().finalize(session, output)

    assert output.is_file()
    assert output.stat().st_size > 500


def test_finalize_rejects_session_without_audio_chunks(tmp_path: Path) -> None:
    session = tmp_path / "session"
    (session / "chunks" / "remote").mkdir(parents=True)
    (session / "chunks" / "me").mkdir(parents=True)

    with pytest.raises(RuntimeError, match="No audio chunks"):
        LocalAudioFinalizer().finalize(session, tmp_path / "recording.webm")
