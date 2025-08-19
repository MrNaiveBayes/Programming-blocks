from machine import ADC, Pin, PWM, I2C, SoftI2C
import time


########################电机##########################
class MOTOR:  # 单例实现
    def __init__(self):
        if not hasattr(self, 'pwm1'):
            print("MOTOR PWM")
            self.pwm1 = PWM(Pin(33, Pin.OUT))
            self.pwm1.freq(1000)
            self.pwm2 = PWM(Pin(34, Pin.OUT))
            self.pwm2.freq(1000)
            self.pwm3 = PWM(Pin(21, Pin.OUT))
            self.pwm3.freq(1000)
            self.pwm4 = PWM(Pin(21, Pin.OUT))  # 26
            self.pwm4.freq(1000)

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            print("MOTOR __new__")
            MOTOR._instance = super().__new__(cls)
        return MOTOR._instance


def start_motor(port, speed):
    if not isinstance(speed, int):
        raise ValueError("电机速度参数speed类型错误，需为-100~100之间的int整型")
    speed_int = int(speed)  # 确保speed为整数
    if speed_int < -100:
        print("电机速度参数speed超限（需在-100到100之间），当前参数值小于-100，被修改为-100")
        speed_int = -100
    elif speed_int > 100:
        print("电机速度参数speed超限（需在-100到100之间），当前参数值大于100，被修改为100")
        speed_int = 100

    if port not in {1, 2}:
        raise ValueError("port口名称错误，需为1或者2")

    duty1 = 0
    duty2 = 0
    if speed_int >= 0:
        duty1 = int(65535 * speed_int / 100)
    else:
        duty2 = int(65535 * (-speed_int) / 100)

    motor = MOTOR()
    if port == 1:
        motor.pwm1.duty_u16(duty1)
        motor.pwm2.duty_u16(duty2)
    else:
        motor.pwm3.duty_u16(duty1)
        motor.pwm4.duty_u16(duty2)


#######################舵机##########################
class SERVO:
    def __init__(self):
        if not hasattr(self, 'pwm'):
            self.pwm = PWM(Pin(45, Pin.OUT))
            self.pwm.freq(50)

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            SERVO._instance = super().__new__(cls)
        return SERVO._instance


def servo_angle(angle=180):
    # PWM频率50hz，波形长度500~2500us，占空比对应2.5%~12.5%
    anglePercent = int(angle * 10 / 360)
    percent = 2.5 + anglePercent
    duty1 = int(percent / 100 * 65535)
    servo = SERVO()
    servo.pwm.duty_u16(duty1)


def _get_pin_by_port(port):
    if not isinstance(port, int):
        raise ValueError("端口需为1~4之间的int整型")
    if port > 4 or port < 1:
        raise ValueError("端口需为1~4之间的int整型")
    if port == 1:
        return Pin(12, Pin.OUT)
    elif port == 2:
        return Pin(13, Pin.OUT)
    elif port == 3:
        return Pin(14, Pin.OUT)
    else:
        return Pin(18, Pin.OUT)


######################三色LED灯#########################
class LED:
    def __init__(self, port):
        if not hasattr(self, 'pwm'):
            print("__init__", self)
            pin = _get_pin_by_port(port)
            self._port = port
            self.pwm = PWM(pin)
        else:
            if self._port != port:
                print("reinit")
                self.pwm.deinit()
                pin = _get_pin_by_port(port)
                self._port = port
                self.pwm = PWM(pin)
                self.pwm.freq(1000)

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            print("__new__", cls)
            LED._instance = super().__new__(cls)
        return LED._instance


def led_set(port, percent):
    if not isinstance(percent, int):
        raise ValueError("percent需为0~100之间的int整型")
    if percent > 100 or percent < 0:
        raise ValueError("percent需为0~100之间的int整型")
    led = LED(port)
    led.pwm.duty_u16(int(percent / 100 * 65535))


########################蜂鸣器############################
class BUZZER:
    def __init__(self, port):
        if not hasattr(self, 'pwm'):
            print("__init__")
            pin = _get_pin_by_port(port)
            self._port = port
            self.pwm = PWM(pin)
        else:
            if self._port != port:
                print("reinit")
                self.pwm.deinit()
                pin = _get_pin_by_port(port)
                self._port = port
                self.pwm = PWM(pin)

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            print("__new__")
            BUZZER._instance = super().__new__(cls)
        return BUZZER._instance


# freq频率, 可听见声音的频率范围为20-20000hz
def buzzer_start(port, freq, duty=512):
    bz = BUZZER(port)
    bz.pwm.freq(freq)
    bz.pwm.duty(duty)


def buzzer_stop(port):
    bz = BUZZER(port)
    bz.pwm.duty_u16(0)


def buzzer_play(port, melodies, wait, duty):  # 定义播放的音乐，等待的时间，占空比
    bz = BUZZER(port)
    for note in melodies:
        if note:
            bz.pwm.freq(note)
        bz.pwm.duty(duty)
        time.sleep(wait/1000)
        bz.pwm.duty(0)
        time.sleep(0.01)
    # 暂停PWM，将占空比设置为0
    bz.pwm.duty(0)


########################I2C设备定义###########################
SENSOR_MAP = {
    0x07: "颜色传感器",
    0x08: "九轴传感器",
    0x0B: "温湿度传感器",
}

I2C_ADDR_SWAT = 0xC2 >> 1
I2C_ADDR_COLOR_SENSOR = 0xC4 >> 1
I2C_ADDR_G_SENSOR = 0xC6 >> 1


class ZC_I2C:
    def __init__(self):
        if not hasattr(self, 'i2c'):
            self.i2c = SoftI2C(scl=Pin(40), sda=Pin(41), freq=100000, timeout=50000)
            self.slaves_list = self.i2c.scan()

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            print("__new__")
            ZC_I2C._instance = super().__new__(cls)
        return ZC_I2C._instance

    def init(self, addr, sensor_num):
        try:
            if addr not in self.slaves_list:
                return False
            data = self.i2c.readfrom_mem(addr, 0x88, 5)
            if data[0] != 0x88 or data[1] != 0x03:
                print("模块外接传感器无响应")
                return False
            if data[2] != 1:
                print("模块外接传感器初始化失败")
                return False
            if sensor_num != data[3]:
                s1 = SENSOR_MAP.get(sensor_num, "未知设备")
                s2 = SENSOR_MAP.get(data[3], "未知设备")
                print(f"模块外接传感器类型错误,期望:{s1}, 模块返回:{s2}")
                return False
            return True
        except Exception as e:
            print(f"初始化错误: {e}")
            return False


####################颜色光线传感器############################
def color_sensor_init():
    device = ZC_I2C()
    ret = device.init(I2C_ADDR_COLOR_SENSOR, 0x07)
    if not ret:
        return False
    print("开始白平衡校准")
    data = bytearray([0x87, 0x02, 0xAA, 0x33])
    device.i2c.writeto(I2C_ADDR_COLOR_SENSOR, data)  # IIC地址，数据
    time.sleep(10)
    data = device.i2c.readfrom_mem(I2C_ADDR_COLOR_SENSOR, 0x87, 6)  # IIC地址，寄存器地址，读取几个字节
    if data[2] == 0x00:
        print("校准成功\n\n")
        return True
    else:
        print("校准失败\n\n")
        return False


def color_sensor_get_rgb():
    device = ZC_I2C()
    try:
        data = device.i2c.readfrom_mem(I2C_ADDR_COLOR_SENSOR, 0x07, 0x0B)  # IIC地址，寄存器地址，读取几个字节
        hex_bytes = [f'{byte:02x}' for byte in data]
        print(hex_bytes)
        menu_RGB_data = [0, 0, 0]
        menu_C_data = ((data[-9] << 8) & 0xff00) + data[-8]
        menu_RGB_data[0] = ((data[-7] << 8) & 0xff00) + data[-6]
        menu_RGB_data[1] = ((data[-5] << 8) & 0xff00) + data[-4]
        menu_RGB_data[2] = ((data[-3] << 8) & 0xff00) + data[-2]
        decrease_data = max(1, max(menu_RGB_data) // 255 + 1)
        menu_RGB_data = [value // decrease_data for value in menu_RGB_data]
        menu_RGB_data.insert(0, 1)
        return menu_RGB_data

    except Exception as error:
        return [0, 0, 0, 0]


###################加速度传感器############################
def process_short_int_data(byte1, byte2):
    value = (byte1 << 8) | byte2
    # 检查最高位是否为1
    if value & 0x8000:
        # 处理为负数
        value = -((~value + 1) & 0xFFFF)

    return value


def G_sensor_get_data():
    device = ZC_I2C()
    ret = device.init(I2C_ADDR_G_SENSOR, 0x08)
    if not ret:
        return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    data = device.i2c.readfrom_mem(I2C_ADDR_G_SENSOR, 0x08, 21)  # IIC地址，寄存器地址，读取几个字节
    aX = process_short_int_data(data[2], data[3])
    aY = process_short_int_data(data[4], data[5])
    aZ = process_short_int_data(data[6], data[7])
    gsX = process_short_int_data(data[8], data[9])
    gsY = process_short_int_data(data[10], data[11])
    gsZ = process_short_int_data(data[12], data[13])
    gmX = process_short_int_data(data[14], data[15])
    gmY = process_short_int_data(data[16], data[17])
    gmZ = process_short_int_data(data[18], data[19])
    return 1, aX, aY, aZ, gsX, gsY, gsZ, gmX, gmY, gmZ


###################温度湿度传感器驱动############################
def get_temperature_humidity():
    device = ZC_I2C()
    ret = device.init(I2C_ADDR_SWAT, 0x0B)
    if not ret:
        return 0, 0, 0
    data = device.i2c.readfrom_mem(I2C_ADDR_SWAT, 0x0B, 7)  # IIC地址，寄存器地址，读取几个字节
    humidity = data[2] + data[3] / 100.0
    temperature_decimal = data[5]
    if temperature_decimal & 0x80:
        temperature_decimal = temperature_decimal & 0x7F  # 取低7位
        temperature = - (data[4] + temperature_decimal / 100.0)
    else:
        temperature = data[4] + temperature_decimal / 100.0
    return 1, humidity, temperature


