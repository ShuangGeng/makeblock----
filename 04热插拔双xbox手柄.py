# dual_serial_two_xbox.py
import asyncio
import serial_asyncio
import vgamepad as vg

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

# Mapping to Xbox buttons
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


# ------------ 每个串口对应一个实例 ----------------
class PS2GamepadProtocol(asyncio.Protocol):
    def __init__(self, port_name):
        self.buffer = [0] * 16
        self.prev = 0
        self.index = 0
        self.start = False

        self.port_name = port_name
        self.pad = vg.VX360Gamepad()   # 每个串口初始化一个虚拟 XBOX 手柄

    def connection_made(self, transport):
        print(f"🎮 已连接：{self.port_name}")
        self.transport = transport

    def connection_lost(self, exc):
        print(f"⚠️ 串口断开：{self.port_name}")
        try:
            self.pad.reset()
            self.pad.update()
        except:
            pass

    def data_received(self, data):
        for byte in data:
            c = byte & 0xFF

            # 帧头
            if c == 0x55 and not self.start and self.prev == 0xFF:
                self.index = 1
                self.start = True
            else:
                self.prev = c
                if self.start and self.index < len(self.buffer):
                    self.buffer[self.index] = c

            self.index += 1

            # 完整帧
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

    # ----------------- 按键 + 摇杆处理 ------------------
    def handle_frame(self):
        bx = self.buffer

        # 摇杆映射
        def map_stick(v):
            v = v - 128
            if v == -128:
                v = -127
            return int(v * 256)  # -32768~32767

        LX = map_stick(bx[2])
        LY = -map_stick(bx[4])
        RX = map_stick(bx[6])
        RY = -map_stick(bx[8])

        self.pad.left_joystick(x_value=LX, y_value=LY)
        self.pad.right_joystick(x_value=RX, y_value=RY)

        # 数字按键
        for name, (buf_index, mask) in PS2_DIGITAL.items():
            pressed = (bx[buf_index] & mask) != 0
            if name in XBOX_MAP:
                if pressed:
                    self.pad.press_button(button=XBOX_MAP[name])
                else:
                    self.pad.release_button(button=XBOX_MAP[name])

        # L2 / R2 → Xbox 触发器
        L2 = 255 if (bx[3] & 0x08) else 0
        R2 = 255 if (bx[3] & 0x02) else 0

        self.pad.left_trigger(value=L2)
        self.pad.right_trigger(value=R2)

        self.pad.update()


# ---------------- 启动多个串口 ----------------
async def start_multi_handpads(port_list):
    loop = asyncio.get_running_loop()

    for port in port_list:
        print(f"⏳ 正在连接 {port} ...")

        await serial_asyncio.create_serial_connection(
            loop,
            lambda p=port: PS2GamepadProtocol(p),
            port,
            baudrate=115200
        )

    print("🎉 所有手柄已启动，尽情游戏！")
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    # 你只需要改这里 —— 每个串口绑定一个虚拟 Xbox
    PORTS = ["COM3", "COM4"]

    asyncio.run(start_multi_handpads(PORTS))
