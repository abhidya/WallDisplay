import ctypes
import socket
import sys
from typing import Set


IFF_UP = 0x1
IFF_LOOPBACK = 0x8


if sys.platform.startswith(("darwin", "freebsd")):
    class Sockaddr(ctypes.Structure):
        _fields_ = [
            ("sa_len", ctypes.c_uint8),
            ("sa_family", ctypes.c_uint8),
            ("sa_data", ctypes.c_ubyte * 14),
        ]


    class SockaddrIn(ctypes.Structure):
        _fields_ = [
            ("sin_len", ctypes.c_uint8),
            ("sin_family", ctypes.c_uint8),
            ("sin_port", ctypes.c_ushort),
            ("sin_addr", ctypes.c_ubyte * 4),
            ("sin_zero", ctypes.c_ubyte * 8),
        ]
else:
    class Sockaddr(ctypes.Structure):
        _fields_ = [
            ("sa_family", ctypes.c_ushort),
            ("sa_data", ctypes.c_ubyte * 14),
        ]


    class SockaddrIn(ctypes.Structure):
        _fields_ = [
            ("sin_family", ctypes.c_ushort),
            ("sin_port", ctypes.c_ushort),
            ("sin_addr", ctypes.c_ubyte * 4),
            ("sin_zero", ctypes.c_ubyte * 8),
        ]


class IfAddrs(ctypes.Structure):
    pass


IfAddrs._fields_ = [
    ("ifa_next", ctypes.POINTER(IfAddrs)),
    ("ifa_name", ctypes.c_char_p),
    ("ifa_flags", ctypes.c_uint),
    ("ifa_addr", ctypes.POINTER(Sockaddr)),
    ("ifa_netmask", ctypes.c_void_p),
    ("ifa_ifu", ctypes.c_void_p),
    ("ifa_data", ctypes.c_void_p),
]


def _is_usable_ipv4(address: str) -> bool:
    if not address or address.startswith("127.") or address.startswith("169.254.") or address == "0.0.0.0":
        return False
    try:
        socket.inet_aton(address)
    except OSError:
        return False
    return True


def _getifaddrs_ipv4_addresses() -> Set[str]:
    libc = ctypes.CDLL(None)
    ifap = ctypes.POINTER(IfAddrs)()
    result = libc.getifaddrs(ctypes.byref(ifap))
    if result != 0:
        return set()

    addresses: Set[str] = set()
    current = ifap
    try:
        while current:
            entry = current.contents
            if entry.ifa_addr and (entry.ifa_flags & IFF_UP) and not (entry.ifa_flags & IFF_LOOPBACK):
                sockaddr = entry.ifa_addr.contents
                if sockaddr.sa_family == socket.AF_INET:
                    sockaddr_in = ctypes.cast(entry.ifa_addr, ctypes.POINTER(SockaddrIn)).contents
                    address = socket.inet_ntoa(bytes(sockaddr_in.sin_addr))
                    if _is_usable_ipv4(address):
                        addresses.add(address)
            current = entry.ifa_next
    finally:
        libc.freeifaddrs(ifap)

    return addresses


def get_local_ipv4_addresses() -> Set[str]:
    addresses = set()

    try:
        addresses.update(_getifaddrs_ipv4_addresses())
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        addresses.update(socket.gethostbyname_ex(hostname)[2])
        for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None, socket.AF_INET):
            if family == socket.AF_INET and sockaddr:
                addresses.add(sockaddr[0])
    except OSError:
        pass

    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            addresses.add(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass

    return {address for address in addresses if _is_usable_ipv4(address)}
