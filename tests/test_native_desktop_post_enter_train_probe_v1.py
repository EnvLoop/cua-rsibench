"""Fake-guest tests for bounded train-only post-Enter raw capture."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageDraw

from native_desktop_factory.post_enter_train_probe_v1 import PostEnterProbeProxy
from native_desktop_factory import v066_post_enter_train_calibration_audit_v1 as audit


def png(color: str) -> bytes:
    image = Image.new("RGB", (1280, 800), "white")
    ImageDraw.Draw(image).rectangle((40, 300, 140, 340), fill=color)
    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


class Guest:
    def __init__(self, frames: list[bytes], *, titles: list[str] | None = None):
        self.frames = frames
        self.titles = titles or ["train.xlsx - LibreOffice Calc"] * len(frames)
        self.index = 0
        self.actions = []

    def get_current_window_id(self):
        return "document" if "train.xlsx" in self.titles[
            min(self.index, len(self.titles) - 1)] else "modal"

    def get_window_title(self, _window_id):
        return self.titles[min(self.index, len(self.titles) - 1)]

    def screenshot(self):
        frame = self.frames[min(self.index, len(self.frames) - 1)]
        self.index += 1
        return frame

    def press(self, key):
        self.actions.append(key)


class ProbeTests(unittest.TestCase):
    def make_probe(self, guest, directory):
        root = Path(directory)
        output = root / "calc"
        output.mkdir()
        current_ns = [0]
        def clock():
            current_ns[0] += 1_000_000
            return current_ns[0]
        waits = []
        def sleeper(seconds):
            waits.append(seconds)
            current_ns[0] += int(seconds * 1_000_000_000)
        proxy = PostEnterProbeProxy(
            guest, storage_root=root, output=output,
            document_filename="train.xlsx", clock=clock, sleep=sleeper)
        return proxy, output, waits

    def test_stable_after_material_transition_logs_five_frames(self):
        with TemporaryDirectory() as directory:
            a, b = png("red"), png("blue")
            guest = Guest([a, b, b, b, b])
            proxy, output, waits = self.make_probe(guest, directory)
            proxy.press("enter")
            rows = [json.loads(line) for line in
                    (output / "post-enter-samples.ndjson").read_text().splitlines()]
            self.assertEqual(len(rows), 5)
            self.assertEqual(len({x["full_frame_sha256"] for x in rows}), 2)
            self.assertEqual(rows[-1]["application_frame_sha256"],
                             rows[-2]["application_frame_sha256"])
            self.assertEqual(waits, [0.25] * 4)
            self.assertTrue(all(x["document_window_stable"] for x in rows))
            self.assertTrue(all((output / Path(x["frame"]["private_path"]).name).is_file()
                                for x in rows))
            self.assertEqual(guest.actions, ["enter"])

    def test_modal_or_oscillation_stops_without_next_action(self):
        a, b = png("red"), png("blue")
        for frames, titles in [
            ([a, b, a, b, a], None),
            ([a, b, a, b, b], None),
            ([a, b, b, b, b],
             ["train.xlsx - LibreOffice Calc", "train.xlsx - LibreOffice Calc",
              "Confirm Save", "Confirm Save", "Confirm Save"]),
        ]:
            with self.subTest(modal=titles is not None), TemporaryDirectory() as directory:
                guest = Guest(frames, titles=titles)
                proxy, output, _waits = self.make_probe(guest, directory)
                with self.assertRaises(ValueError):
                    proxy.press("enter")
                self.assertEqual(guest.actions, ["enter"])
                self.assertTrue((output / "post-enter-samples.ndjson").is_file())

    def test_non_enter_is_transparent_and_third_enter_refused(self):
        with TemporaryDirectory() as directory:
            guest = Guest([png("red")] * 10)
            proxy, output, _waits = self.make_probe(guest, directory)
            proxy.press("esc")
            self.assertFalse((output / "post-enter-samples.ndjson").exists())
            proxy.press("enter")
            proxy.press("enter")
            with self.assertRaises(ValueError):
                proxy.press("enter")
            self.assertEqual(guest.actions, ["esc", "enter", "enter"])

    def test_independent_raw_audit_detects_frame_tamper(self):
        with TemporaryDirectory() as directory:
            a, b = png("red"), png("blue")
            guest = Guest([a, b, b, b, b] * 2)
            proxy, output, _waits = self.make_probe(guest, directory)
            proxy.press("enter")
            proxy.press("enter")
            value = audit._post_enter_samples(output_root=Path(directory))
            self.assertEqual(value["raw_frames"], 10)
            (output / "post-enter-01-04.png").write_bytes(a)
            with self.assertRaisesRegex(ValueError, "frame changed"):
                audit._post_enter_samples(output_root=Path(directory))


if __name__ == "__main__":
    unittest.main()
