"""
FRD950 / Impinj E710 TCP client (Len + CRC16 protocol).

Usage:
    from frd950.client import Frd950

    with Frd950("192.168.1.190") as r:
        r.configure_mexico_toll(power_dbm=33, antennas=[1])
        for tag in r.listen_realtime(seconds=30):
            print(tag.epc, tag.rssi)
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional


DEFAULT_HOST = "192.168.1.190"
DEFAULT_PORT = 6000

# Antenna bit for 0x3F mux / inventory Ant code
ANT_MUX = {1: 0x01, 2: 0x02, 3: 0x04, 4: 0x08}
ANT_INV = {1: 0x80, 2: 0x81, 3: 0x82, 4: 0x83}

STATUS = {
    0x00: "OK",
    0x01: "inventory_ok",
    0x02: "inventory_timeout",
    0x03: "more_data",
    0x04: "memory_full",
    0x26: "inventory_stats",
    0x28: "heartbeat",
    0xF8: "antenna_error",
    0xF9: "exec_error",
    0xFA: "op_failed",
    0xFB: "no_tag",
    0xFC: "tag_error",
    0xFD: "length_error",
    0xFE: "illegal_command",
    0xFF: "parameter_error",
}


def crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def build_frame(addr: int, cmd: int, data: bytes = b"") -> bytes:
    body = bytes([addr & 0xFF, cmd & 0xFF]) + data
    partial = bytes([len(body) + 2]) + body
    return partial + crc16(partial)


def parse_frames(buf: bytes) -> list[bytes]:
    out: list[bytes] = []
    i = 0
    while i < len(buf):
        ln = buf[i]
        if ln < 4 or i + 1 + ln > len(buf):
            break
        out.append(buf[i : i + 1 + ln])
        i += 1 + ln
    return out


def fre_byte(b7: int, b6: int, n: int) -> int:
    return ((b7 & 1) << 7) | ((b6 & 1) << 6) | (n & 0x3F)


@dataclass
class TagRead:
    epc: str
    rssi: Optional[int] = None
    ant_mask: Optional[int] = None
    count: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)


@dataclass
class ReaderInfo:
    fw_major: int
    fw_minor: int
    reader_type: int
    tr_type: int
    dmaxfre: int
    dminfre: int
    power_dbm: int
    scan_time: int
    ant_cfg: int
    check_ant: int

    @property
    def supports_6c(self) -> bool:
        return bool(self.tr_type & 0x02)

    @property
    def supports_6b(self) -> bool:
        return bool(self.tr_type & 0x01)


class Frd950Error(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None, raw: bytes = b""):
        super().__init__(message)
        self.status = status
        self.raw = raw


class Frd950:
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        addr: int = 0x00,
        timeout: float = 5.0,
    ):
        self.host = host
        self.port = port
        self.addr = addr
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None

    def connect(self) -> "Frd950":
        s = socket.create_connection((self.host, self.port), timeout=self.timeout)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s.settimeout(0.2)
        self._sock = s
        return self

    def close(self) -> None:
        if self._sock is not None:
            try:
                # Best-effort leave answer mode
                self._sock.sendall(build_frame(self.addr, 0x76, bytes([0x00])))
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def __enter__(self) -> "Frd950":
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def sock(self) -> socket.socket:
        if self._sock is None:
            raise Frd950Error("not connected")
        return self._sock

    def drain(self, wait: float = 1.0) -> bytes:
        end = time.time() + wait
        buf = bytearray()
        self.sock.settimeout(0.15)
        while time.time() < end:
            try:
                chunk = self.sock.recv(8192)
                if not chunk:
                    break
                buf.extend(chunk)
                end = max(end, time.time() + 0.25)
            except socket.timeout:
                if buf:
                    break
        return bytes(buf)

    def transact(self, cmd: int, data: bytes = b"", wait: float = 1.5) -> bytes:
        self.sock.sendall(build_frame(self.addr, cmd, data))
        return self.drain(wait)

    def require_ok(self, raw: bytes, what: str) -> bytes:
        if len(raw) < 4:
            raise Frd950Error(f"{what}: empty response", raw=raw)
        status = raw[3]
        if status != 0x00:
            name = STATUS.get(status, "?")
            raise Frd950Error(f"{what}: status=0x{status:02x} ({name})", status=status, raw=raw)
        return raw

    # ---- high-level config ----

    def set_answer_mode(self) -> None:
        self.require_ok(self.transact(0x76, bytes([0x00])), "set_answer_mode")

    def set_realtime_mode(self) -> None:
        self.require_ok(self.transact(0x76, bytes([0x01])), "set_realtime_mode")

    def set_power_dbm(self, dbm: int) -> None:
        if not 0 <= dbm <= 33:
            raise ValueError("power 0..33 dBm")
        self.require_ok(self.transact(0x2F, bytes([dbm & 0xFF])), f"set_power_{dbm}")

    def set_scan_time(self, units_100ms: int) -> None:
        self.require_ok(self.transact(0x25, bytes([units_100ms & 0xFF])), "set_scan_time")

    def set_antenna_check(self, enabled: bool) -> None:
        self.require_ok(
            self.transact(0x66, bytes([0x01 if enabled else 0x00])),
            "set_antenna_check",
        )

    def select_antennas(self, antennas: Iterable[int], persist: bool = False) -> None:
        mask = 0
        for a in antennas:
            if a not in ANT_MUX:
                raise ValueError(f"antenna must be 1..4, got {a}")
            mask |= ANT_MUX[a]
        if not persist:
            mask |= 0x80
        self.require_ok(self.transact(0x3F, bytes([mask])), "select_antennas")

    def set_frequency(self, maxfre: int, minfre: int) -> None:
        self.require_ok(
            self.transact(0x22, bytes([maxfre & 0xFF, minfre & 0xFF])),
            "set_frequency",
        )

    def set_region_us(self) -> None:
        """US classic 902.75–927.25 MHz (N=0..49)."""
        self.set_frequency(fre_byte(0, 0, 49), fre_byte(1, 0, 0))

    def set_region_us3(self) -> None:
        """US band3 902–928 MHz (N=0..52)."""
        self.set_frequency(fre_byte(1, 1, 52), fre_byte(0, 0, 0))

    def set_region_mexico_toll(self) -> None:
        """México peaje IAVE/PASE/Televía: ISO 18000-6C @ 902–928 MHz."""
        self.set_region_us3()

    def set_region_eu(self) -> None:
        self.set_frequency(fre_byte(0, 1, 14), fre_byte(0, 0, 0))

    def set_region_eu3(self) -> None:
        self.set_frequency(fre_byte(1, 0, 3), fre_byte(0, 1, 0))

    def configure_mexico_toll(
        self,
        power_dbm: int = 33,
        antennas: Optional[list[int]] = None,
        antenna_check: bool = False,
    ) -> ReaderInfo:
        """Preset listo para tags de caseta México."""
        if antennas is None:
            antennas = [1]
        self.set_answer_mode()
        self.set_region_mexico_toll()
        self.set_power_dbm(power_dbm)
        self.set_antenna_check(antenna_check)
        self.select_antennas(antennas, persist=False)
        return self.get_info()

    def get_info(self) -> ReaderInfo:
        raw = self.transact(0x21, wait=2.0)
        self.require_ok(raw, "get_info")
        # may be single frame
        pkt = parse_frames(raw)[0]
        d = pkt[4:-2]
        if len(d) < 12:
            raise Frd950Error("get_info: short payload", raw=raw)
        return ReaderInfo(
            fw_major=d[0],
            fw_minor=d[1],
            reader_type=d[2],
            tr_type=d[3],
            dmaxfre=d[4],
            dminfre=d[5],
            power_dbm=d[6],
            scan_time=d[7],
            ant_cfg=d[8],
            check_ant=d[11],
        )

    def measure_return_loss(self, freq_mhz: float, antenna: int = 1) -> int:
        if antenna not in (1, 2, 3, 4):
            raise ValueError("antenna 1..4")
        khz = int(round(freq_mhz * 1000))
        data = khz.to_bytes(4, "big") + bytes([antenna - 1])
        raw = self.transact(0x91, data, wait=2.0)
        self.require_ok(raw, "return_loss")
        pkt = parse_frames(raw)[0]
        return pkt[4]

    def set_realtime_params(
        self,
        protocol_6c: bool = True,
        pause_code: int = 0,
        filter_time: int = 0,
        q: int = 4,
        session: int = 1,
    ) -> None:
        """
        pause_code: 0=10ms,1=20ms,2=30ms,3=50ms,4=100ms
        filter_time: 0=no dedupe; N = N seconds
        """
        proto = 0x00 if protocol_6c else 0x01
        data = bytes([proto, pause_code & 0xFF, filter_time & 0xFF, q & 0x3F, session & 0xFF])
        self.require_ok(self.transact(0x75, data), "set_realtime_params")

    def listen_realtime(
        self,
        seconds: float = 30.0,
        q: int = 4,
        session: int = 1,
        filter_time: int = 0,
        pause_code: int = 0,
    ) -> list[TagRead]:
        """Enter realtime, collect tags, always restore answer mode."""
        acc: dict[str, TagRead] = {}
        self.set_realtime_params(True, pause_code, filter_time, q, session)
        self.set_realtime_mode()
        t0 = time.time()
        try:
            while time.time() - t0 < seconds:
                for pkt in parse_frames(self.drain(0.4)):
                    if len(pkt) < 6 or pkt[2] != 0xEE or pkt[3] != 0x00:
                        continue
                    data = pkt[4:-2]
                    if len(data) < 3:
                        continue
                    elen = data[1]
                    if len(data) < 2 + elen + 1:
                        continue
                    epc = data[2 : 2 + elen].hex().upper()
                    rssi = data[2 + elen]
                    ant = data[0]
                    now = time.time()
                    if epc in acc:
                        acc[epc].count += 1
                        acc[epc].rssi = rssi
                        acc[epc].last_seen = now
                    else:
                        acc[epc] = TagRead(epc=epc, rssi=rssi, ant_mask=ant, first_seen=now, last_seen=now)
        finally:
            try:
                self.set_answer_mode()
            except Frd950Error:
                self.sock.sendall(build_frame(self.addr, 0x76, bytes([0x00])))
                self.drain(1.0)
        return sorted(acc.values(), key=lambda t: -t.count)

    def inventory_once(
        self,
        antenna: int = 1,
        q: int = 4,
        session: int = 1,
        target: int = 0,
        scan_time_100ms: int = 10,
        with_stats: bool = False,
    ) -> list[str]:
        """Single answer-mode inventory; returns EPC hex strings."""
        if antenna not in ANT_INV:
            raise ValueError("antenna 1..4")
        qv = (q & 0x0F) | (0x80 if with_stats else 0)
        data = bytes([qv, session & 0xFF, target & 0xFF, ANT_INV[antenna], scan_time_100ms & 0xFF])
        raw = self.transact(0x01, data, wait=scan_time_100ms * 0.1 + 1.0)
        epcs: list[str] = []
        for pkt in parse_frames(raw):
            if len(pkt) < 6 or pkt[2] != 0x01:
                continue
            status, payload = pkt[3], pkt[4:-2]
            if status == 0x26:
                continue
            if status in (0x01, 0x02, 0x03, 0x04) and len(payload) >= 2 and payload[1] > 0:
                num, blob = payload[1], payload[2:]
                if num and len(blob) % num == 0:
                    elen = len(blob) // num
                    for i in range(num):
                        epcs.append(blob[i * elen : (i + 1) * elen].hex().upper())
        return epcs


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="FRD950 quick listen")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--seconds", type=float, default=20)
    p.add_argument("--ant", type=int, default=1)
    p.add_argument("--power", type=int, default=33)
    args = p.parse_args()

    with Frd950(args.host, args.port) as r:
        info = r.configure_mexico_toll(power_dbm=args.power, antennas=[args.ant])
        print(
            f"FW {info.fw_major}.{info.fw_minor} power={info.power_dbm} dBm "
            f"6C={info.supports_6c} antcfg=0x{info.ant_cfg:02x}"
        )
        try:
            rl = r.measure_return_loss(915.25, args.ant)
            print(f"return_loss ant{args.ant} @915.25MHz = {rl} dB")
        except Frd950Error as e:
            print(f"return_loss: {e}")

        tags = r.listen_realtime(seconds=args.seconds)
        if not tags:
            print("Sin tags")
        for t in tags:
            print(f"{t.epc}  ×{t.count}  rssi=0x{(t.rssi or 0):02x}")


if __name__ == "__main__":
    main()
