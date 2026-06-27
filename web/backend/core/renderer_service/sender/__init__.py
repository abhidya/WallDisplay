"""
Sender implementations for the Renderer Service.

This package contains classes for sending content to different types of display devices:
- DirectSender: Local display output
- DLNASender: DLNA-compatible devices
- AirPlaySender: AirPlay-compatible devices
- HDMISender: Local HDMI display/projector output
"""

from .base import Sender


def __getattr__(name):
    if name == 'DirectSender':
        from .direct import DirectSender
        return DirectSender
    if name == 'DLNASender':
        from .dlna import DLNASender
        return DLNASender
    if name == 'AirPlaySender':
        from .airplay import AirPlaySender
        return AirPlaySender
    if name == 'HDMISender':
        from .hdmi import HDMISender
        return HDMISender
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'Sender',
    'DirectSender',
    'DLNASender',
    'AirPlaySender',
    'HDMISender',
]
