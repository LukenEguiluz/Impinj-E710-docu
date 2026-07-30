#!/usr/bin/env python3
"""Inventory en answer mode (un disparo / varios ciclos) en una antena."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frd950 import Frd950


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="192.168.1.190")
    p.add_argument("--port", type=int, default=6000)
    p.add_argument("--ant", type=int, default=1, choices=(1, 2, 3, 4))
    p.add_argument("--power", type=int, default=33)
    p.add_argument("--cycles", type=int, default=10)
    args = p.parse_args()

    seen: dict[str, int] = {}
    with Frd950(args.host, args.port) as r:
        r.configure_mexico_toll(power_dbm=args.power, antennas=[args.ant])
        print(f"Answer inventory ant{args.ant} ×{args.cycles}\n")
        for i in range(args.cycles):
            epcs = r.inventory_once(antenna=args.ant, q=4, session=1, scan_time_100ms=10)
            for e in epcs:
                seen[e] = seen.get(e, 0) + 1
                print(f"  [{i+1}] {e}")
            if not epcs:
                print(f"  [{i+1}] (sin tags)")
            time.sleep(0.1)

    print("\nResumen:")
    if not seen:
        print("  Sin tags")
    for e, n in sorted(seen.items(), key=lambda x: -x[1]):
        print(f"  {e}  ×{n}")


if __name__ == "__main__":
    main()
