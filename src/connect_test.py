"""connect_test.py — PX4'e bağlanır, sağlık durumunu ve uçuş modunu bir kez okur."""
import asyncio
from mavsdk import System


async def main():
    drone = System()
    await drone.connect(system_address="udpin://0.0.0.0:14540")
    print("Bağlanılıyor...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Bağlandı!")
            break
    async for h in drone.telemetry.health():
        print("GPS:", h.is_global_position_ok,
              "| Home:", h.is_home_position_ok,
              "| Arm edilebilir:", h.is_armable)
        break
    async for fm in drone.telemetry.flight_mode():
        print("Uçuş modu:", fm)
        break

asyncio.run(main())
