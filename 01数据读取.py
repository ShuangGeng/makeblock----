
import serial
import time

class MePS2:
    def __init__(self, port='COM3', baudrate=9600):
        """
        初始化串口和手柄状态。
        :param port: 串口号（如 'COM3')
        :param baudrate: 波特率，默认 9600
        """
        self.serial = serial.Serial(port, baudrate, timeout=1)
        self.buffer = [0] * 10  # 模拟 MePS2 的 buffer，9 字节数据 + 校验和
        self.ps2_data_list = {
            'LX': 128, 'LY': 128, 'RX': 128, 'RY': 128,  # 摇杆默认中值
            'R1': False, 'R2': False, 'L1': False, 'L2': False,
            'MODE': False, 'TRIANGLE': False, 'XSHAPED': False,
            'SQUARE': False, 'ROUND': False, 'START': False,
            'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False,
            'SELECT': False, 'BUTTON_L': False, 'BUTTON_R': False
        }
        self.ps2_data_list_bak = self.ps2_data_list.copy()  # 备份状态
        self.is_ready = False
        self.is_start = False
        self.index = 0
        self.prev_c = 0
        self.last_time = time.time()


    def read_serial(self):
        """
        读取串口数据，模拟 MePS2::readSerial。
        """
        if self.serial.in_waiting > 0:
            return self.serial.read(1)[0]  # 读取 1 字节
        return None

    def read_joystick(self):
        """
        读取手柄数据，模拟 MePS2::readjoystick。
        :return: True 如果数据有效,False 否则
        """
        current_time = time.time()
        # 超时重置（200ms 未收到数据）
        if current_time - self.last_time > 0.2:
            self.is_ready = False
            self.is_start = False
            self.prev_c = 0x00
            self.buffer[2] = self.buffer[4] = self.buffer[6] = self.buffer[8] = 0x80  # 摇杆中值
            self.buffer[1] = self.buffer[3] = self.buffer[5] = self.buffer[7] = 0x00  # 按键清零

        data = self.read_serial()
        while data is not None:
            self.last_time = current_time
            c = data & 0xFF
            if c == 0x55 and not self.is_start and self.prev_c == 0xFF:
                self.index = 1
                self.is_start = True
            else:
                self.prev_c = c
                if self.is_start:
                    self.buffer[self.index] = c
            self.index += 1

            # 数据帧结束或错误处理
            if not self.is_start and self.index > 12:
                self.index = 0
                self.is_start = False
                self.buffer[2] = self.buffer[4] = self.buffer[6] = self.buffer[8] = 0x80
                self.buffer[1] = self.buffer[3] = self.buffer[5] = self.buffer[7] = 0x00
            elif self.is_start and self.index > 9:
                # 校验和验证
                checksum = sum(self.buffer[2:9]) & 0xFF
                if checksum == self.buffer[9]:
                    self.is_ready = True
                    self.is_start = False
                    self.index = 0
                    return True
                else:
                    self.is_start = False
                    self.index = 0
                    self.prev_c = 0x00
                    return False
            data = self.read_serial()
        return False

    def me_analog(self, button):
        """
        读取摇杆模拟量，模拟 MePS2::MeAnalog。
        :param button: 'LX', 'LY', 'RX', 'RY'
        :return: 模拟值 (-255 到 255)，错误时返回 0
        """
        if not self.is_ready:
            return 0
        if button in ['LX', 'LY', 'RX', 'RY']:
            result = 2 * (self.ps2_data_list[button] - 128)
            if button in ['LY', 'RY']:
                result = -result  # Y 轴反转
            if result in [-256, -254]:
                result = -255
            elif result in [254, 256]:
                result = 255
            return result
        return 0

    def button_pressed(self, button):
        """
        检查按键是否按下，模拟 MePS2::ButtonPressed。
        :param button: 按键名称（如 'TRIANGLE', 'START')
        :return: True 如果按下,False 否则
        """
        if not self.is_ready:
            return self.ps2_data_list_bak[button]
        self.ps2_data_list_bak[button] = self.ps2_data_list[button]
        return self.ps2_data_list[button]

    def loop(self):
        """
        更新手柄状态，模拟 MePS2::loop。
        """
        if self.read_joystick():
            # 更新摇杆数据
            self.ps2_data_list['LX'] = self.buffer[2]
            self.ps2_data_list['LY'] = self.buffer[4]
            self.ps2_data_list['RX'] = self.buffer[6]
            self.ps2_data_list['RY'] = self.buffer[8]
            # 更新按键数据
            self.ps2_data_list['R1'] = (self.buffer[3] & 0x01) == 0x01
            self.ps2_data_list['R2'] = (self.buffer[3] & 0x02) == 0x02
            self.ps2_data_list['L1'] = (self.buffer[3] & 0x04) == 0x04
            self.ps2_data_list['L2'] = (self.buffer[3] & 0x08) == 0x08
            self.ps2_data_list['MODE'] = (self.buffer[3] & 0x10) == 0x10
            self.ps2_data_list['TRIANGLE'] = (self.buffer[5] & 0x01) == 0x01
            self.ps2_data_list['XSHAPED'] = (self.buffer[5] & 0x02) == 0x02
            self.ps2_data_list['SQUARE'] = (self.buffer[5] & 0x04) == 0x04
            self.ps2_data_list['ROUND'] = (self.buffer[5] & 0x08) == 0x08
            self.ps2_data_list['START'] = (self.buffer[5] & 0x10) == 0x10
            self.ps2_data_list['UP'] = (self.buffer[7] & 0x01) == 0x01
            self.ps2_data_list['DOWN'] = (self.buffer[7] & 0x02) == 0x02
            self.ps2_data_list['LEFT'] = (self.buffer[7] & 0x04) == 0x04
            self.ps2_data_list['RIGHT'] = (self.buffer[7] & 0x08) == 0x08
            self.ps2_data_list['SELECT'] = (self.buffer[7] & 0x10) == 0x10
            self.ps2_data_list['BUTTON_L'] = (self.buffer[3] & 0x20) == 0x20
            self.ps2_data_list['BUTTON_R'] = (self.buffer[7] & 0x20) == 0x20

        

    def close(self):
        """
        关闭串口连接。
        """
        self.serial.close()

# 测试代码
if __name__ == "__main__":
    ps2_a = MePS2(port='COM3', baudrate=115200)  # 替换为你的串口号
    ps2_b = MePS2(port='COM4', baudrate=115200)  # 替换为你的串口号
    ps2=[ps2_a,ps2_b]
    try:
        while True:
            for i in range(0,2):
                ps2[i].loop()
                # 打印部分数据以调试

                if ps2[i].button_pressed('R1'):
                    print("R1 pressed")
                elif ps2[i].button_pressed('L1'):
                    print("L1 pressed")
                elif ps2[i].button_pressed('R2'):
                    print("R2 pressed")
                elif ps2[i].button_pressed('L2'):
                    print("L2 pressed")

                elif ps2[i].button_pressed('TRIANGLE'):
                    print("TRIANGLE pressed")
                elif ps2[i].button_pressed('XSHAPED'):
                    print("XSHAPED pressed")
                elif ps2[i].button_pressed('SQUARE'):
                    print("SQUARE pressed")
                elif ps2[i].button_pressed('ROUND'):
                    print("ROUND pressed")

                elif ps2[i].button_pressed('UP'):
                    print("UP pressed")
                elif ps2[i].button_pressed('DOWN'):
                    print("DOWN pressed")
                elif ps2[i].button_pressed('LEFT'):
                    print("LEFT pressed")
                elif ps2[i].button_pressed('RIGHT'):
                    print("RIGHT pressed")
                
                elif ps2[i].button_pressed('SELECT'):
                    print("SELECT pressed")
                elif ps2[i].button_pressed('START'):
                    print("START pressed")
                elif ps2[i].button_pressed('BUTTON_L'):
                    print("BUTTON_L pressed")
                elif ps2[i].button_pressed('BUTTON_R'):
                    print("BUTTON_R pressed")

                print(ps2[i].me_analog('LX'), ps2[i].me_analog('LY'), ps2[i].me_analog('RX'), ps2[i].me_analog('RY'))

    except KeyboardInterrupt:
        print("程序退出")
        ps2.close()