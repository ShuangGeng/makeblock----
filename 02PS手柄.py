#模拟ps手柄
import asyncio
import serial_asyncio
import vgamepad as vg
import sys


PS2_DIGITAL = {
    "R1": (3, 0x01),
    "R2": (3, 0x02),
    "L1": (3, 0x04),
    "L2": (3, 0x08),

    "TRIANGLE": (5, 0x01),
    "XSHAPED": (5, 0x02),    # X
    "SQUARE": (5, 0x04),
    "ROUND": (5, 0x08),      # O
    "START": (5, 0x10),

    "UP": (7, 0x01),
    "DOWN": (7, 0x02),
    "LEFT": (7, 0x04),
    "RIGHT": (7, 0x08),
    "SELECT": (7, 0x10),
    # MODE mapped to special PS button
    "MODE": (3, 0x10),
}

# PS2 -> DS4 按钮映射（根据你本地的 DS4_BUTTONS 枚举命名）
DS4_MAP = {
    "XSHAPED": vg.DS4_BUTTONS.DS4_BUTTON_CROSS,
    "ROUND": vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE,
    "TRIANGLE": vg.DS4_BUTTONS.DS4_BUTTON_SQUARE,
    "SQUARE": vg.DS4_BUTTONS.DS4_BUTTON_CIRCLE,

    "L1": vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT,
    "R1": vg.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT,

    "START": vg.DS4_BUTTONS.DS4_BUTTON_OPTIONS,
    "SELECT": vg.DS4_BUTTONS.DS4_BUTTON_SHARE,
}

# DPAD uses HAT (DS4_DPAD_DIRECTIONS)
DPAD_MAP = {
    (True, False, False, False): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH,
    (True, False, False, True):  vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHEAST,
    (False, False, False, True): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST,
    (False, True, False, True):  vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHEAST,
    (False, True, False, False): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH,
    (False, True, True, False):  vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHWEST,
    (False, False, True, False): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST,
    (True, False, True, False):  vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHWEST,
    (False, False, False, False): vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE,
}

# 可选：摇杆死区（float 0..1）
DEADZONE = 0.06


class MePS2Protocol(asyncio.Protocol):
    def __init__(self, deadzone=DEADZONE):
        self.buffer = [0] * 16
        self.prev = 0
        self.index = 0
        self.start = False
        self.pad = vg.VDS4Gamepad()  # 虚拟 DS4 手柄
        self.deadzone = deadzone

    def connection_made(self, transport):
        print("🎮 Serial connected. PS2 -> Virtual DS4 running.")
        self.transport = transport

        # wake device by a tiny press-release (some drivers require)
        try:
            self.pad.press_button(button=vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE)
            self.pad.update()
            self.pad.release_button(button=vg.DS4_BUTTONS.DS4_BUTTON_TRIANGLE)
            self.pad.update()
        except Exception:
            # 忽略唤醒失败
            pass

    def data_received(self, data):
        # data 是 bytes，可以一次包含多帧，逐字节解析
        for byte in data:
            c = byte & 0xFF
            if c == 0x55 and not self.start and self.prev == 0xFF:
                self.index = 1
                self.start = True
            else:
                self.prev = c
                if self.start and self.index < len(self.buffer):
                    self.buffer[self.index] = c

            self.index += 1

            # 超过最大长度表明错位，重置
            if not self.start and self.index > 12:
                self.index = 0
            # 一帧接收完（按原 Arduino 实现 index > 9）
            elif self.start and self.index > 9:
                checksum = sum(self.buffer[2:9]) & 0xFF
                if checksum == self.buffer[9]:
                    # valid frame
                    self.start = False
                    self.index = 0
                    try:
                        self.handle_frame()
                    except Exception as e:
                        print("handle_frame error:", e, file=sys.stderr)
                else:
                    # invalid -> reset
                    self.start = False
                    self.index = 0
                    self.prev = 0

    # 将 0~255 映射为 -1.0 .. 1.0 float（并应用死区）
    def map_stick_float(self, v):
        f = (v - 128) / 128.0
        if abs(f) < self.deadzone:
            return 0.0
        # clamp
        if f > 1.0:
            f = 1.0
        if f < -1.0:
            f = -1.0
        return f

    def map_trigger_float(self, pressed_bit):
        # PS2 L2/R2 在 MePS2 协议是数字位（按下或未按下）
        # 把按下映射为 1.0，否则 0.0
        return 1.0 if pressed_bit else 0.0

    def handle_frame(self):
        bx = self.buffer  # alias

        # 摇杆 -> float
        lx_f = self.map_stick_float(bx[2])
        ly_f = self.map_stick_float(bx[4])  # Y 轴取反以符合游戏习惯
        rx_f = self.map_stick_float(bx[6])
        ry_f = self.map_stick_float(bx[8])

        # set float joysticks
        # 使用 float 接口（-1.0 .. 1.0）
        self.pad.left_joystick_float(x_value_float=lx_f, y_value_float=ly_f)
        self.pad.right_joystick_float(x_value_float=rx_f, y_value_float=ry_f)

        # 按键（普通按钮）
        for name, (idx, mask) in PS2_DIGITAL.items():
            pressed = (bx[idx] & mask) != 0

            if name == "MODE":
                # MODE -> PS special button
                if pressed:
                    self.pad.press_special_button(special_button=vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS)
                else:
                    self.pad.release_special_button(special_button=vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS)
            else:
                if name in DS4_MAP:
                    ds4_btn = DS4_MAP[name]
                    if pressed:
                        self.pad.press_button(button=ds4_btn)
                    else:
                        self.pad.release_button(button=ds4_btn)

        # DPAD (八向 HAT)
        up = (bx[7] & 0x01) != 0
        down = (bx[7] & 0x02) != 0
        left = (bx[7] & 0x04) != 0
        right = (bx[7] & 0x08) != 0

        dpad_dir = DPAD_MAP.get((up, down, left, right), vg.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE)
        # directional_pad expects DS4_DPAD_DIRECTIONS enum value
        try:
            self.pad.directional_pad(dpad_dir)
        except Exception:
            # 某些 vgamepad 版本可能名称不同，保底尝试按键 press/release
            # 这里不做额外处理以避免重复逻辑
            pass

        # L2 / R2 触发器（float 版本）
        l2_pressed = (bx[3] & 0x08) != 0
        r2_pressed = (bx[3] & 0x02) != 0
        self.pad.left_trigger_float(value_float=self.map_trigger_float(l2_pressed))
        self.pad.right_trigger_float(value_float=self.map_trigger_float(r2_pressed))

        # Touchpad click? （如果需要）
        # PS2 协议没有 touchpad，但可以用某个按键映射触摸板点击（可选）
        # 例如把 SELECT 映射为 touchpad click:
        if (bx[7] & 0x10) != 0:
            self.pad.press_special_button(special_button=vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD)
        else:
            self.pad.release_special_button(special_button=vg.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD)

        # 提交更新（必须）
        self.pad.update()

        # debug 可选（取消注释以打印）
        # print(f"LX:{lx_f:.2f} LY:{ly_f:.2f} RX:{rx_f:.2f} RY:{ry_f:.2f} L2:{l2_pressed} R2:{r2_pressed}")

    def connection_lost(self, exc):
        # 在断开时重置虚拟手柄状态
        try:
            self.pad.reset()
            self.pad.update()
        except Exception:
            pass
        print("Serial connection lost")


async def run(port, baudrate):
    loop = asyncio.get_running_loop()
    await serial_asyncio.create_serial_connection(loop, lambda: MePS2Protocol(), port, baudrate=baudrate)
    # 保持运行
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    # CLI 参数：端口与波特率
    port = "COM11" if sys.platform.startswith("win") else "/dev/ttyUSB0"
    baud = 115200
    if len(sys.argv) >= 2:
        port = sys.argv[1]
    if len(sys.argv) >= 3:
        baud = int(sys.argv[2])
    print(f"Starting PS2 -> DS4 bridge on {port}@{baud}")
    try:
        asyncio.run(run(port, baud))
    except KeyboardInterrupt:
        print("Exiting")
