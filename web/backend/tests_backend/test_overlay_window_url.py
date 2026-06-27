from web.backend.core.overlay_window_url import build_overlay_window_url


def test_build_overlay_window_url_handles_projection_and_capture_params():
    assert build_overlay_window_url(
        "http://wall.local/",
        projector_id="proj-hdmi",
        mode="overlay",
        config_id=7,
        controls_hidden=True,
        hide_widgets=True,
        capture_mode="dlna",
        extra_params={"debug": True, "skip": None},
    ) == (
        "http://wall.local/backend-static/overlay_window.html?"
        "projector_id=proj-hdmi&mode=overlay&config_id=7&controls=hidden&"
        "widgets=hidden&capture=dlna&debug=true"
    )
