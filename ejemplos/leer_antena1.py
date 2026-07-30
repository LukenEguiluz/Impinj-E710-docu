#!/usr/bin/env python3
"""Lectura realtime antena 1 — preset México peaje 902–928 MHz."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frd950 import Frd950


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="192.168.1.190")
    p.add_argument("--port", type=int, default=6000)
    p.add_argument("--ant", type=int, default=1, choices=(1, 2, 3, 4))
    p.add_argument("--power", type=int, default=33)
    p.add_argument("--seconds", type=float, default=30)
    args = p.parse_args()

    with Frd950(args.host, args.port) as r:
        info = r.configure_mexico_toll(power_dbm=args.power, antennas=[args.ant])
        print(
            f"Conectado FW {info.fw_major}.{info.fw_minor} | "
            f"{args.power} dBm | ant {args.ant} | 902-928 MHz"
        )
        print(f"Escuchando {args.seconds:.0f}s...\n")
        tags = r.listen_realtime(seconds=args.seconds, q=4, session=1, filter_time=0)
        if not tags:
            print("Sin tags.")
            return
        print(f"{'EPC':<32} {'×':>4}  RSSI")
        print("-" * 48)
        for t in tags:
            rssi = f"0x{t.rssi:02x}" if t.rssi is not None else "-"
            print(f"{t.epc:<32} {t.count:>4}  {rssi}")


if __name__ == "__main__":
    main()
