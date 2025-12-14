# 模拟xbox手柄
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

# 映射到 Xbox 按键
XBOX_MAP = {
    "XSHAPED": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,   
    "ROUND": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
    "SQUARE": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "TRIANGLE": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,  

    "L1": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "R1": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,

    "UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,

    "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
    "SELECT": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
}


class MePS2Protocol(asyncio.Protocol):
    def __init__(self):
        self.buffer = [0]*16
        self.prev = 0
        self.index = 0
        self.start = False

        self.pad = vg.VX360Gamepad()

    def connection_made(self, transport):
        print("🎮 已连接 PS2 手柄")
        self.transport = transport

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

            if not self.start and self.index > 12:
                self.index = 0

            elif self.start and self.index > 9:
                checksum = sum(self.buffer[2:9]) & 0xFF
                if checksum == self.buffer[9]:
                    self.start = False
                    self.index = 0
                    self.handle_frame()
                else:
                    self.start = False
                    self.index = 0
                    self.prev = 0

    # --- 主数据解析 ---
    def handle_frame(self):
        bx = self.buffer

        # 摇杆（0~255 → -32768~32767）
        def map_stick(v):
            v=v-128
            if v==-128:
                v=-127
            return int(v  / 127 * 32767)

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

        # L2 / R2 特殊处理（因为 Xbox 是模拟触发器）
        L2_pressed = (bx[3] & 0x08) != 0
        R2_pressed = (bx[3] & 0x02) != 0

        self.pad.left_trigger(value=255 if L2_pressed else 0)
        self.pad.right_trigger(value=255 if R2_pressed else 0)

        self.pad.update()


async def main():
    port = "COM4"
    baud = 115200

    print(f"连接 {port} ...")

    loop = asyncio.get_running_loop()
    await serial_asyncio.create_serial_connection(
        loop, lambda: MePS2Protocol(), port, baudrate=baud
    )

    print("手柄1 已启动")

    while True:
        await asyncio.sleep(1)




if __name__ == "__main__":
    asyncio.run(main())
