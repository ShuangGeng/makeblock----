# auto_multi_ps2_to_xbox.py
import asyncio
import serial_asyncio
import vgamepad as vg
from serial.tools import list_ports

# PS2 Digital Buttons
PS2_DIGITAL = {
    "R1": (3, 0x01),
    "R2": (3, 0x02),
    "L1": (3, 0x04),
    "L2": (3, 0x08),
    "MODE": (3, 0x10),
    "BUTTON_L": (3, 0x20),

    "TRIANGLE": (5, 0x01),
    "XSHAPED": (5, 0x02),
    "SQUARE": (5, 0x04),
    "ROUND": (5, 0x08),
    "START": (5, 0x10),

    "UP": (7, 0x01),
    "DOWN": (7, 0x02),
    "LEFT": (7, 0x04),
    "RIGHT": (7, 0x08),
    "SELECT": (7, 0x10),
    "BUTTON_R": (7, 0x20),
}

# Xbox mapping
XBOX_MAP = {
    "XSHAPED": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "SQUARE": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "TRIANGLE": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "ROUND": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,

    "L1": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "R1": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,

    "UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,

    "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
    "SELECT": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
}


# ================== 基础解析类 =====================
class PS2GamepadProtocol(asyncio.Protocol):
    def __init__(self, port_name, remove_callback):
        self.buffer = [0] * 16
        self.prev = 0
        self.index = 0
        self.start = False

        self.port_name = port_name
        self.pad = vg.VX360Gamepad()

        self.remove_callback = remove_callback

    def connection_made(self, transport):
        print(f"🎮 [连接] {self.port_name}")
        self.transport = transport

    def connection_lost(self, exc):
        print(f"⚠️ [断开] {self.port_name}")
        try:
            self.pad.reset()
            self.pad.update()
        except:
            pass
        self.remove_callback(self.port_name)

    def data_received(self, data):
        for byte in data:
            c = byte & 0xFF

            if c == 0x55 and not self.start and self.prev == 0xFF:
                self.index = 1
                self.start = True
            else:
                self.prev = c
                if self.start:
                    self.buffer[self.index] = c

            self.index += 1

            if self.start and self.index > 9:
                checksum = sum(self.buffer[2:9]) & 0xFF
                if checksum == self.buffer[9]:
                    self.start = False
                    self.index = 0
                    self.handle_frame()
                else:
                    self.start = False
                    self.index = 0
                    self.prev = 0

            elif not self.start and self.index > 12:
                self.index = 0

    # ================== 解析帧 =====================
    def handle_frame(self):
        bx = self.buffer

        def map_stick(v):
            v = v - 128
            if v == -128:
                v = -127
            return int(v * 256)

        LX = map_stick(bx[2])
        LY = -map_stick(bx[4])
        RX = map_stick(bx[6])
        RY = -map_stick(bx[8])

        self.pad.left_joystick(x_value=LX, y_value=LY)
        self.pad.right_joystick(x_value=RX, y_value=RY)

        for name, (buf_index, mask) in PS2_DIGITAL.items():
            pressed = (bx[buf_index] & mask) != 0
            if name in XBOX_MAP:
                if pressed:
                    self.pad.press_button(button=XBOX_MAP[name])
                else:
                    self.pad.release_button(button=XBOX_MAP[name])

        L2 = 255 if (bx[3] & 0x08) else 0
        R2 = 255 if (bx[3] & 0x02) else 0

        self.pad.left_trigger(value=L2)
        self.pad.right_trigger(value=R2)

        self.pad.update()


# ================== 热插拔管理类 =====================
class GamepadManager:
    def __init__(self):
        self.active_ports = {}  # port -> (transport, protocol)

    def remove_port(self, port):
        if port in self.active_ports:
            print(f"🔥 移除手柄实例：{port}")
            del self.active_ports[port]

    async def scan_ports(self):
        ports = [p.device for p in list_ports.comports()]
        return ports

    async def manage_hotplug(self):
        loop = asyncio.get_running_loop()

        while True:
            ports = await self.scan_ports()

            # 检查新增端口
            for p in ports:
                if p not in self.active_ports:
                    print(f"➕ 新设备：{p}")

                    try:
                        transport, protocol = await serial_asyncio.create_serial_connection(
                            loop,
                            lambda pn=p: PS2GamepadProtocol(pn, self.remove_port),
                            p,
                            baudrate=115200
                        )
                        self.active_ports[p] = (transport, protocol)
                        print(f"🎮 Xbox 手柄已创建：{p}")

                    except Exception as e:
                        print(f"❌ 无法打开 {p}: {e}")

            # 检查移除的端口
            for p in list(self.active_ports.keys()):
                if p not in ports:
                    print(f"➖ 设备移除：{p}")

                    transport, protocol = self.active_ports[p]
                    transport.close()

            await asyncio.sleep(1)  # 1秒扫描一次


# ================== 主程序 =====================
async def main():
    manager = GamepadManager()
    print("🔍 正在监控串口热插拔 ...")

    await manager.manage_hotplug()


if __name__ == "__main__":
    asyncio.run(main())
