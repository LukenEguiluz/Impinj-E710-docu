#!/usr/bin/env python3
"""Mide return loss en las 4 antenas (diagnóstico de cableado RF)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frd950 import Frd950, Frd950Error


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="192.168.1.190")
    p.add_argument("--port", type=int, default=6000)
    p.add_argument("--mhz", type=float, default=915.25)
    p.add_argument("--power", type=int, default=33)
    args = p.parse_args()

    with Frd950(args.host, args.port) as r:
        r.set_answer_mode()
        r.set_region_mexico_toll()
        r.set_power_dbm(args.power)
        r.set_antenna_check(False)
        print(f"Return loss @ {args.mhz} MHz (potencia {args.power} dBm)\n")
        print(f"{'Ant':<6} {'RL dB':>6}  Diagnóstico")
        print("-" * 40)
        for ant in (1, 2, 3, 4):
            try:
                r.select_antennas([ant], persist=False)
                rl = r.measure_return_loss(args.mhz, ant)
                ok = "OK" if rl >= 6 else "REVISAR cable/antena"
                print(f"{ant:<6} {rl:>6}  {ok}")
            except Frd950Error as e:
                print(f"{ant:<6} {'err':>6}  {e}")


if __name__ == "__main__":
    main()
