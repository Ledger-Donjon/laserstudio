from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass

import cv2


@dataclass(frozen=True)
class ResolutionProbeResult:
    """Outcome of probing one candidate resolution."""

    requested: tuple[int, int]
    reported: tuple[int, int]
    captured: tuple[int, int] | None
    fps: float | None
    works: bool


def generate_resolution_candidates(*, thorough: bool = False) -> list[tuple[int, int]]:
    """
    Build resolution pairs to try when probing a camera.

    This is only used during discovery; supported modes are inferred from
    what the driver actually captures, not from this list.

    :param thorough: When False (default), use a small set of anchor sizes
        for a faster probe (~15 candidates). When True, sweep more sizes.
    """
    if thorough:
        bases = (160, 320, 480, 640, 800, 1024, 1280, 1600, 1920, 2560, 3840)
        ratios = ((4, 3), (16, 9), (5, 4), (3, 2), (1, 1))
    else:
        bases = (160, 320, 640, 1280, 1920)
        ratios = ((4, 3), (16, 9), (5, 4))

    candidates: set[tuple[int, int]] = set()
    for base in bases:
        for ratio_w, ratio_h in ratios:
            candidates.add((base, base * ratio_h // ratio_w))
            if thorough and ratio_w != ratio_h:
                candidates.add((base * ratio_w // ratio_h, base))
    return sorted(candidates, key=lambda size: (size[0] * size[1], size[0]))


def _open_capture(index: int, backend: int | None) -> cv2.VideoCapture:
    if backend is None:
        return cv2.VideoCapture(index)
    return cv2.VideoCapture(index, backend)


def _discard_frames(cap: cv2.VideoCapture, count: int) -> None:
    for _ in range(count):
        cap.read()


def probe_supported_resolutions(
    index: int | None = 0,
    *,
    cap: cv2.VideoCapture | None = None,
    candidates: list[tuple[int, int]] | None = None,
    warmup_frames: int = 1,
    verify_capture: bool = True,
    backend: int | None = None,
    thorough: bool = False,
) -> list[ResolutionProbeResult]:
    """
    Probe a USB camera for resolutions that OpenCV can apply and capture.

    Pass an existing ``cap`` to probe without closing the device (e.g. from
    ``CameraUSBInstrument``). The initial resolution is restored afterwards.
    """
    candidates = candidates or generate_resolution_candidates(thorough=thorough)
    own_cap = cap is None
    if own_cap:
        cap = _open_capture(index or 0, backend)
    assert cap is not None

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {index or 0}")

    initial = (
        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    )
    results: list[ResolutionProbeResult] = []
    seen_captured: set[tuple[int, int]] = set()

    try:
        default_w, default_h = initial
        _discard_frames(cap, warmup_frames)
        ret, frame = cap.read()
        default_captured = (
            (int(frame.shape[1]), int(frame.shape[0]))
            if ret and frame is not None
            else None
        )
        results.append(
            ResolutionProbeResult(
                requested=(default_w, default_h),
                reported=(default_w, default_h),
                captured=default_captured,
                fps=float(cap.get(cv2.CAP_PROP_FPS)) or None,
                works=default_captured is not None if verify_capture else cap.isOpened(),
            )
        )
        if default_captured is not None:
            seen_captured.add(default_captured)

        for width, height in candidates:
            if (width, height) == (default_w, default_h):
                continue

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            reported = (
                int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            )
            fps = float(cap.get(cv2.CAP_PROP_FPS)) or None

            if verify_capture and reported in seen_captured:
                continue

            captured: tuple[int, int] | None = None
            works = False
            if verify_capture:
                _discard_frames(cap, warmup_frames)
                ret, frame = cap.read()
                if ret and frame is not None:
                    captured = (int(frame.shape[1]), int(frame.shape[0]))
                    works = captured == reported or captured == (width, height)
            else:
                works = reported == (width, height)

            if verify_capture and captured is not None:
                if captured in seen_captured:
                    continue
                seen_captured.add(captured)
                works = True

            if works:
                results.append(
                    ResolutionProbeResult(
                        requested=(width, height),
                        reported=reported,
                        captured=captured,
                        fps=fps,
                        works=True,
                    )
                )
    finally:
        if not own_cap:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, initial[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, initial[1])
            _discard_frames(cap, warmup_frames)
        else:
            cap.release()

    return results


def native_resolutions(
    cap: cv2.VideoCapture,
    *,
    warmup_frames: int = 1,
    candidates: list[tuple[int, int]] | None = None,
    thorough: bool = False,
) -> list[tuple[int, int]]:
    """Return unique captured frame sizes discovered on an open capture device."""
    results = probe_supported_resolutions(
        cap=cap,
        candidates=candidates,
        warmup_frames=warmup_frames,
        verify_capture=True,
        thorough=thorough,
    )
    native: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for result in results:
        if result.captured is None or result.captured in seen:
            continue
        seen.add(result.captured)
        native.append(result.captured)
    return sorted(native, key=lambda size: (size[0] * size[1], size[0]))


def _backend_from_name(name: str) -> int:
    key = f"CAP_{name.upper()}"
    backend = getattr(cv2, key, None)
    if backend is None:
        raise ValueError(f"Unknown OpenCV backend '{name}'")
    return int(backend)


def list_camera_resolutions(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe supported resolutions for a USB camera via OpenCV."
    )
    parser.add_argument(
        "index",
        nargs="?",
        type=int,
        default=0,
        help="Camera index (default: 0)",
    )
    parser.add_argument(
        "--backend",
        help="OpenCV capture backend name (e.g. AVFOUNDATION, V4L2, DSHOW)",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=1,
        help="Frames to discard after each resolution change (default: 1)",
    )
    parser.add_argument(
        "--thorough",
        action="store_true",
        help="Probe more candidate resolutions (slower, more exhaustive)",
    )
    parser.add_argument(
        "--no-capture",
        action="store_true",
        help="Only check CAP_PROP values, do not verify with frame capture",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print results as JSON",
    )
    args = parser.parse_args(argv)

    backend = _backend_from_name(args.backend) if args.backend else None
    try:
        results = probe_supported_resolutions(
            args.index,
            warmup_frames=args.warmup_frames,
            verify_capture=not args.no_capture,
            backend=backend,
            thorough=args.thorough,
        )
        if args.no_capture:
            native = sorted(
                {
                    result.reported
                    for result in results
                    if result.works and result.reported[0] > 0 and result.reported[1] > 0
                },
                key=lambda size: (size[0] * size[1], size[0]),
            )
        else:
            native = []
            seen: set[tuple[int, int]] = set()
            for result in results:
                if result.captured is None or result.captured in seen:
                    continue
                seen.add(result.captured)
                native.append(result.captured)
            native.sort(key=lambda size: (size[0] * size[1], size[0]))
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "native_resolutions": [list(size) for size in native],
            "probe_details": [asdict(result) for result in results],
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(
        f"Camera index {args.index} — {len(native)} native resolution(s):\n"
    )
    for width, height in native:
        print(f"  {width}x{height}")

    if native and results:
        print("\nProbe details:\n")
        for result in results:
            if result.captured is None:
                continue
            req = f"{result.requested[0]}x{result.requested[1]}"
            cap_size = f"{result.captured[0]}x{result.captured[1]}"
            snapped = " *" if result.requested != result.captured else ""
            fps = f"{result.fps:.1f}" if result.fps is not None else "n/a"
            print(f"  requested {req:>12}  ->  frame {cap_size:>12}  |  fps {fps}{snapped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(list_camera_resolutions())
