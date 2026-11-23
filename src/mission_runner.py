#!/usr/bin/env python3
"""
mission_runner.py
-----------------
QGroundControl'de hazirlanip PX4'e YUKLENMIS bir gorevi (mission) MAVSDK ile
baslatir, ilerlemesini izler ve telemetriyi terminale basar (bonus).

Akis:
  1) PX4'e baglan            (core.connection_state)
  2) Saglik kontrolu          (telemetry.health -> GPS / home / armable)
  3) Yuklu gorevi kontrol et  (mission_raw.download_mission)
  4) Arm + gorevi baslat      (action.arm, mission_raw.start_mission)
  5) Ilerlemeyi + telemetriyi izle
  6) Inis ve disarm'i bekle

NOT: QGC'nin "Fixed Wing Landing Pattern"i DO_LAND_START gibi ogeler uretir.
MAVSDK'nin yuksek seviyeli `mission` eklentisi bu ogeleri temsil edemedigi icin
burada `mission_raw` kullaniliyor.

Kullanim:
  python3 mission_runner.py                       # varsayilan: udpin://0.0.0.0:14540
  python3 mission_runner.py --url udp://:14540    # eski MAVSDK surumleri icin
"""

import argparse
import asyncio
import math
import sys

from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.mission_raw import MissionRawError
from mavsdk.telemetry import LandedState

# Sik gorulen MAVLink komut numaralari -> okunur isim
MAV_CMD_NAMES = {
    16: "NAV_WAYPOINT",
    17: "NAV_LOITER_UNLIM",
    19: "NAV_LOITER_TIME",
    20: "NAV_RETURN_TO_LAUNCH",
    21: "NAV_LAND",
    22: "NAV_TAKEOFF",
    31: "NAV_LOITER_TO_ALT",
    178: "DO_CHANGE_SPEED",
    189: "DO_LAND_START",
}

# Telemetri gorevlerinin doldurdugu ortak durum
state = {
    "lat": None, "lon": None, "rel_alt": None,
    "ground_speed": None, "airspeed": None, "climb": None,
    "flight_mode": "?", "landed": "?", "armed": False,
    "battery": None, "wp": "-/-",
}


# ---------------------------------------------------------------- yardimcilar
async def wait_connected(drone: System, timeout: float) -> None:
    print("[1/6] PX4'e baglaniliyor...")

    async def _wait():
        async for cs in drone.core.connection_state():
            if cs.is_connected:
                return

    await asyncio.wait_for(_wait(), timeout)
    print("      Baglandi.")


async def wait_healthy(drone: System, timeout: float) -> None:
    print("[2/6] Saglik kontrolu (GPS, home konumu, arm edilebilirlik)...")

    async def _wait():
        async for h in drone.telemetry.health():
            armable = getattr(h, "is_armable", True)
            if h.is_global_position_ok and h.is_home_position_ok and armable:
                return

    await asyncio.wait_for(_wait(), timeout)
    print("      Arac hazir.")


async def check_mission(drone: System) -> int:
    print("[3/6] PX4'teki yuklu gorev okunuyor...")
    items = await drone.mission_raw.download_mission()
    if not items:
        raise RuntimeError("PX4'te yuklu gorev yok. Once QGC > Plan > Upload yapin.")

    cmds = [it.command for it in items]
    for i, it in enumerate(items):
        name = MAV_CMD_NAMES.get(it.command, f"CMD_{it.command}")
        print(f"      #{i:02d} {name:<22} alt={it.z:7.1f} m")

    if 22 not in cmds:
        print("      UYARI: Gorevde NAV_TAKEOFF yok.")
    if 21 not in cmds:
        print("      UYARI: Gorevde NAV_LAND yok - sabit kanat inmeden daire cizer.")
    return len(items)


# ---------------------------------------------------------- telemetri gorevleri
async def watch_position(drone):
    async for p in drone.telemetry.position():
        state["lat"], state["lon"] = p.latitude_deg, p.longitude_deg
        state["rel_alt"] = p.relative_altitude_m


async def watch_velocity(drone):
    async for v in drone.telemetry.velocity_ned():
        state["ground_speed"] = math.hypot(v.north_m_s, v.east_m_s)


async def watch_fw_metrics(drone):
    async for m in drone.telemetry.fixedwing_metrics():
        state["airspeed"], state["climb"] = m.airspeed_m_s, m.climb_rate_m_s


async def watch_flight_mode(drone):
    async for fm in drone.telemetry.flight_mode():
        state["flight_mode"] = fm.name


async def watch_landed(drone):
    async for ls in drone.telemetry.landed_state():
        state["landed"] = ls.name


async def watch_armed(drone):
    async for a in drone.telemetry.armed():
        state["armed"] = a


async def watch_battery(drone):
    async for b in drone.telemetry.battery():
        state["battery"] = b.remaining_percent


async def watch_progress(drone):
    async for mp in drone.mission_raw.mission_progress():
        state["wp"] = f"{mp.current}/{mp.total}"


def fmt(x, nd=1, unit=""):
    return "  --  " if x is None else f"{x:.{nd}f}{unit}"


async def printer(period: float):
    while True:
        bat = state["battery"]
        # MAVSDK surumune gore 0-1 ya da 0-100 gelebilir
        if bat is not None and bat <= 1.0:
            bat *= 100
        print(
            f"WP {state['wp']:>5} | {state['flight_mode']:<12} | "
            f"{state['landed']:<10} | arm={'E' if state['armed'] else 'H'} | "
            f"lat {fmt(state['lat'], 6)} lon {fmt(state['lon'], 6)} | "
            f"irtifa {fmt(state['rel_alt'], 1, 'm')} | "
            f"yer hizi {fmt(state['ground_speed'], 1, 'm/s')} | "
            f"hava hizi {fmt(state['airspeed'], 1, 'm/s')} | "
            f"tirmanma {fmt(state['climb'], 1, 'm/s')} | "
            f"pil {fmt(bat, 0, '%')}"
        )
        await asyncio.sleep(period)


# ----------------------------------------------------------------- ana akis
async def run(args) -> int:
    drone = System()
    await drone.connect(system_address=args.url)

    try:
        await wait_connected(drone, args.timeout)
        await wait_healthy(drone, args.timeout)
        total = await check_mission(drone)
    except asyncio.TimeoutError:
        print("HATA: Zaman asimi. PX4 SITL calisiyor mu, port dogru mu?")
        return 1
    except (RuntimeError, MissionRawError) as e:
        print(f"HATA: {e}")
        return 1

    watchers = [
        asyncio.create_task(f(drone)) for f in (
            watch_position, watch_velocity, watch_fw_metrics, watch_flight_mode,
            watch_landed, watch_armed, watch_battery, watch_progress,
        )
    ]
    show = asyncio.create_task(printer(args.period))

    try:
        print("[4/6] Arm ediliyor ve gorev baslatiliyor...")
        await drone.mission_raw.set_current_mission_item(0)
        await drone.action.arm()
        await drone.mission_raw.start_mission()

        print("[5/6] Gorev izleniyor...")
        while True:
            await asyncio.sleep(1)
            cur, _, tot = state["wp"].partition("/")
            mission_done = cur.isdigit() and tot.isdigit() and int(cur) >= int(tot) > 0
            on_ground = state["landed"] == LandedState.ON_GROUND.name
            if mission_done and on_ground:
                break

        print("[6/6] Inis tamam. Disarm bekleniyor...")
        for _ in range(30):
            if not state["armed"]:
                break
            await asyncio.sleep(1)
        print("Gorev tamamlandi." if not state["armed"]
              else "Inis tamam ama arac hala arm'li (COM_DISARM_LAND parametresine bakin).")
        return 0

    except (ActionError, MissionRawError) as e:
        print(f"HATA: {e}")
        return 1
    finally:
        for t in watchers + [show]:
            t.cancel()


def main():
    ap = argparse.ArgumentParser(description="QGC'de yuklenen PX4 gorevini baslat ve izle")
    ap.add_argument("--url", default="udpin://0.0.0.0:14540",
                    help="MAVSDK baglanti adresi (eski surumler: udp://:14540)")
    ap.add_argument("--timeout", type=float, default=60.0, help="baglanti/saglik zaman asimi (s)")
    ap.add_argument("--period", type=float, default=1.0, help="telemetri yazdirma araligi (s)")
    args = ap.parse_args()
    try:
        sys.exit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        print("\nKullanici durdurdu. Araci QGC'den RTL/Hold ile kontrol edin.")
        sys.exit(130)


if __name__ == "__main__":
    main()
