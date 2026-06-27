import json
import os
import zipfile
from types import SimpleNamespace

from web.backend.services.structured_lighting_service import StructuredLightingService, _utcnow_iso
from discovery.base import CastingMethod


def test_structured_lighting_session_persists_metadata(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=1280,
        projector_height=720,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    session_file = tmp_path / session["session_id"] / "session.json"

    assert session_file.exists()
    assert session["decode"]["status"] == "not_started"
    assert session["calibration"]["status"] == "not_started"
    assert session["review"]["status"] == "pending"


def test_hdmi_step_presentation_uses_structured_lighting_step_url(monkeypatch, tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)
    service._sessions = {}

    calls = []

    class FakeRendererService:
        def start_projector_url(self, projector_id, content_url, content_mode, options):
            calls.append({
                "projector_id": projector_id,
                "content_url": content_url,
                "content_mode": content_mode,
                "options": options,
            })
            return True

    monkeypatch.setattr(service, "_get_renderer_service", lambda: FakeRendererService(), raising=False)
    monkeypatch.setenv("NANODLNA_SERVER_BASE_URL", "http://controller.local:8088")

    session = service.create_session(
        name="HDMI Wall Calibration",
        projector_device_id="proj-hdmi-local",
        camera_index=1,
        projector_width=1280,
        projector_height=720,
        presentation_mode="hdmi_step",
        hold_ms=1200,
        notes="test run",
    )
    service._worker.update({
        "worker_id": "worker-1",
        "last_seen_at": _utcnow_iso(),
        "connected": True,
    })

    service.start_session(session["session_id"])
    claimed = service.claim_next_step("worker-1")

    assert claimed["step"]["index"] == 0
    assert claimed["presentation_mode"] == "hdmi_step"
    assert calls == [
        {
            "projector_id": "proj-hdmi-local",
            "content_url": (
                f"http://controller.local:8088/api/structured-lighting/sessions/"
                f"{session['session_id']}/steps/0/present?projector_id=proj-hdmi-local"
            ),
            "content_mode": "structured_light_step",
            "options": {
                "session_id": session["session_id"],
                "step_index": 0,
                "step_label": "Reference White",
            },
        }
    ]


def test_record_capture_uses_notebook_reference_filenames(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=1280,
        projector_height=720,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    service.record_capture(session["session_id"], 0, b"white", "white.png")
    service.record_capture(session["session_id"], 1, b"black", "black.png")
    service.record_capture(session["session_id"], 2, b"pattern", "capture.png")

    capture_dir = tmp_path / session["session_id"] / "captures"

    assert (capture_dir / "img_white.png").exists()
    assert (capture_dir / "img_black.png").exists()
    assert (capture_dir / "img_0002.png").exists()


def test_decode_session_fails_cleanly_without_reference_frames(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=1280,
        projector_height=720,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    result = service.decode_session(session["session_id"], sample_step=2)

    assert result["decode"]["status"] == "failed"
    assert "Reference white/black captures are missing" in result["decode"]["message"]
    assert os.path.exists(tmp_path / session["session_id"] / "session.json")


def test_decode_session_persists_calibration_record(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=1280,
        projector_height=720,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    decode_dir = tmp_path / session["session_id"] / "decode"
    decode_dir.mkdir(parents=True, exist_ok=True)
    decode_manifest = decode_dir / "decode_manifest.json"
    decode_manifest.write_text('{"status":"completed"}', encoding="utf-8")

    def fake_decode(session_id, sample_step, tuning_params=None):
        assert session_id == session["session_id"]
        assert sample_step == 2
        assert tuning_params is None
        return {
            "status": "completed",
            "started_at": "2026-03-24T00:00:00",
            "finished_at": "2026-03-24T00:00:01",
            "message": "ok",
            "metrics": {
                "camera_width": 640,
                "camera_height": 480,
                "coverage_ratio": 0.75,
            },
            "artifacts": {
                "decode_dir": str(decode_dir),
                "cam2proj": str(decode_dir / "cam2proj.npy"),
                "proj2cam_x": str(decode_dir / "proj2cam_x.npy"),
                "proj2cam_y": str(decode_dir / "proj2cam_y.npy"),
                "valid_mask_cam": str(decode_dir / "valid_mask_cam.npy"),
            },
        }

    service._decode_graycode_session = fake_decode

    result = service.decode_session(session["session_id"], sample_step=2)
    calibration_path = tmp_path / session["session_id"] / "calibration.json"

    assert result["decode"]["status"] == "completed"
    assert result["calibration"]["status"] == "completed"
    assert result["calibration"]["summary"]["coverage_ratio"] == 0.75
    assert calibration_path.exists()

    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    assert calibration["artifacts"]["decode_manifest"] == str(decode_manifest)


def test_record_capture_clears_stale_derived_outputs(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=1280,
        projector_height=720,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    session_dir = tmp_path / session["session_id"]
    decode_dir = session_dir / "decode"
    decode_dir.mkdir(parents=True, exist_ok=True)
    (decode_dir / "cam2proj.npy").write_bytes(b"stale")
    (session_dir / "calibration.json").write_text('{"status":"completed"}', encoding="utf-8")
    (session_dir / "export_bundle.zip").write_bytes(b"stale")

    service.record_capture(session["session_id"], 0, b"white", "white.png")

    assert not decode_dir.exists()
    assert not (session_dir / "calibration.json").exists()
    assert not (session_dir / "export_bundle.zip").exists()


def test_export_session_bundle_includes_current_session_files(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=1280,
        projector_height=720,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    session_dir = tmp_path / session["session_id"]
    capture_dir = session_dir / "captures"
    capture_dir.mkdir(parents=True, exist_ok=True)
    (capture_dir / "img_white.png").write_bytes(b"white")

    decode_dir = session_dir / "decode"
    decode_dir.mkdir(parents=True, exist_ok=True)
    (decode_dir / "cam2proj.npy").write_bytes(b"decode")

    calibration = {
        "status": "completed",
        "message": "Calibration record generated from Gray-code decode.",
        "generated_at": "2026-03-24T00:00:00",
        "summary": {"coverage_ratio": 0.8},
        "artifacts": {"cam2proj": str(decode_dir / "cam2proj.npy")},
    }
    service._sessions[session["session_id"]]["calibration"] = calibration
    service._sessions[session["session_id"]]["review"] = {
        "status": "accepted",
        "message": "Session accepted for export.",
        "notes": "",
        "reviewed_by": "operator-1",
        "accepted_at": "2026-03-24T00:00:00",
        "updated_at": "2026-03-24T00:00:00",
    }
    service._persist_session(service._sessions[session["session_id"]])

    export_info = service.export_session_bundle(session["session_id"])

    assert export_info["filename"] == f"structured_lighting_{session['session_id']}.zip"
    assert os.path.exists(export_info["export_path"])

    with zipfile.ZipFile(export_info["export_path"], "r") as archive:
        names = set(archive.namelist())

    assert "session.json" in names
    assert "calibration.json" in names
    assert "captures/img_white.png" in names
    assert "decode/cam2proj.npy" in names


def test_export_requires_accepted_review(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=1280,
        projector_height=720,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    try:
        service.export_session_bundle(session["session_id"])
    except RuntimeError as exc:
        assert "accepted" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected export to require accepted review")


def test_artifact_review_lists_available_previews(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=8,
        projector_height=4,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        raise AssertionError("numpy is required for this test")

    decode_dir = tmp_path / session["session_id"] / "decode"
    decode_dir.mkdir(parents=True, exist_ok=True)
    np.save(decode_dir / "cam2proj.npy", np.array([[[0, 0], [7, 3]], [[-1, -1], [4, 2]]], dtype=np.int32))
    np.save(decode_dir / "valid_mask_cam.npy", np.array([[1, 1], [0, 1]], dtype=np.uint8))
    np.save(decode_dir / "proj2cam_x.npy", np.array([[0.0, float("nan")], [1.0, 2.0]], dtype=np.float32))
    np.save(decode_dir / "proj2cam_y.npy", np.array([[0.0, float("nan")], [1.0, 1.0]], dtype=np.float32))

    service._sessions[session["session_id"]]["decode"] = {
        "status": "completed",
        "started_at": "2026-03-24T00:00:00",
        "finished_at": "2026-03-24T00:00:01",
        "message": "ok",
        "metrics": {"coverage_ratio": 0.75},
        "artifacts": {
            "decode_dir": str(decode_dir),
            "cam2proj": str(decode_dir / "cam2proj.npy"),
            "valid_mask_cam": str(decode_dir / "valid_mask_cam.npy"),
            "proj2cam_x": str(decode_dir / "proj2cam_x.npy"),
            "proj2cam_y": str(decode_dir / "proj2cam_y.npy"),
        },
    }

    review = service.get_artifact_review(session["session_id"])

    assert review["coverage_status"] == "good"
    assert review["review"]["status"] == "pending"
    assert {preview["id"] for preview in review["previews"]} == {
        "valid-mask",
        "projector-coverage",
        "cam2proj-xy",
    }


def test_render_artifact_preview_returns_png_bytes(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=8,
        projector_height=4,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        raise AssertionError("numpy is required for this test")

    decode_dir = tmp_path / session["session_id"] / "decode"
    decode_dir.mkdir(parents=True, exist_ok=True)
    np.save(decode_dir / "valid_mask_cam.npy", np.array([[1, 0], [0, 1]], dtype=np.uint8))

    service._sessions[session["session_id"]]["decode"] = {
        "status": "completed",
        "started_at": "2026-03-24T00:00:00",
        "finished_at": "2026-03-24T00:00:01",
        "message": "ok",
        "metrics": {},
        "artifacts": {
            "valid_mask_cam": str(decode_dir / "valid_mask_cam.npy"),
        },
    }

    preview = service.render_artifact_preview(session["session_id"], "valid-mask")

    assert preview is not None
    assert preview.startswith(b"\x89PNG\r\n\x1a\n")


def test_update_review_persists_operator_verdict(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=1280,
        projector_height=720,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    updated = service.update_review(
        session["session_id"],
        verdict="needs_recapture",
        notes="coverage too sparse",
        reviewed_by="abdul",
    )

    assert updated["review"]["status"] == "needs_recapture"
    assert updated["review"]["notes"] == "coverage too sparse"
    assert updated["review"]["reviewed_by"] == "abdul"
    assert updated["review"]["accepted_at"] is None


def test_update_review_acceptance_sets_accepted_at(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=1280,
        projector_height=720,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    updated = service.update_review(
        session["session_id"],
        verdict="accepted",
        notes="good coverage",
        reviewed_by="abdul",
    )

    assert updated["review"]["status"] == "accepted"
    assert updated["review"]["reviewed_by"] == "abdul"
    assert updated["review"]["accepted_at"] is not None


def test_resolve_dlna_projector_falls_back_to_legacy_runtime_device():
    service = StructuredLightingService()
    legacy_device = SimpleNamespace(
        name="Legacy Projector",
        friendly_name="Legacy Projector",
        hostname="10.0.0.45",
        action_url="http://10.0.0.45:3500/upnp/control/AVTransport1",
        location="http://10.0.0.45:3500/description.xml",
        manufacturer="Acme",
    )
    discovery_manager = SimpleNamespace(
        get_device_by_id=lambda _device_id: None,
        get_all_devices=lambda: [],
    )
    runtime = SimpleNamespace(get_devices=lambda: [legacy_device])

    resolved = service._resolve_dlna_projector("dlna_10.0.0.45_3500", discovery_manager, runtime)

    assert resolved is not None
    assert resolved.id == "dlna_10.0.0.45_3500"
    assert resolved.casting_method == CastingMethod.DLNA
    assert resolved.action_url == legacy_device.action_url


def test_cast_to_resolved_device_tracks_session_for_unregistered_device():
    service = StructuredLightingService()
    cast_calls = []

    async def cast_content(device, content_url, content_type, metadata):
        cast_calls.append((device.id, content_url, content_type, metadata))
        return SimpleNamespace(id="session-1")

    backend = SimpleNamespace(cast_content=cast_content)

    class DummyLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    target_device = SimpleNamespace(
        id="dlna_10.0.0.45_3500",
        casting_method=CastingMethod.DLNA,
        action_url="http://10.0.0.45:3500/upnp/control/AVTransport1",
    )
    discovery_manager = SimpleNamespace(
        get_device_by_id=lambda _device_id: None,
        _get_backend_for_device=lambda _device: backend,
        _device_lock=DummyLock(),
        device_sessions={},
    )

    cast_session = service._run_async(
        service._cast_to_resolved_device(
            discovery_manager=discovery_manager,
            target_device=target_device,
            selected_device_id="dlna_10.0.0.45_3500",
            content_url="http://127.0.0.1:9010/step.png",
            content_type="image/png",
            title="Wall Calibration - Reference White",
        )
    )

    assert cast_session.id == "session-1"
    assert discovery_manager.device_sessions["dlna_10.0.0.45_3500"][0].id == "session-1"
    assert cast_calls == [
        (
            "dlna_10.0.0.45_3500",
            "http://127.0.0.1:9010/step.png",
            "image/png",
            {"title": "Wall Calibration - Reference White"},
        )
    ]


def test_render_step_image_for_dlna_returns_jpeg_bytes(tmp_path):
    service = StructuredLightingService()
    service._upload_root = str(tmp_path)

    session = service.create_session(
        name="Wall Calibration",
        projector_device_id="dlna-projector",
        camera_index=1,
        projector_width=16,
        projector_height=8,
        presentation_mode="dlna_step",
        hold_ms=1200,
        notes="test run",
    )

    preview = service.render_step_image_for_dlna(session["session_id"], 0)

    assert preview is not None
    assert preview.startswith(b"\xff\xd8\xff")
