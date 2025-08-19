from machine import Pin, ADC
import neopixel
import machine
import time

# 主菜单数据
main_menu_items = ["LED", "Buzzer", "Motor", "Servo", "Nine axis sensor", "Color sensor", "Temperature and humidity", "BLE"]
# 子屏幕按钮数据
sub_menu_data = {
    "LED": [{"label": "Port", "value": 0, "modifiable": True},
            {"label": "Red", "value": 255, "modifiable": True},
            {"label": "Green", "value": 255, "modifiable": True},
            {"label": "Blue", "value": 255, "modifiable": True},
            {"label": "Brightness", "value": 100, "modifiable": True}],

    "Buzzer": [{"label": "Port", "value": 4, "modifiable": True},
               {"label": "Frequency", "value": 2637, "modifiable": True},
               {"label": "Song_num", "value": 1, "modifiable": True},
               {"label": "Wait_time_ms", "value": 250, "modifiable": True},
               {"label": "Duty", "value": 512, "modifiable": True}],

    "Motor": [{"label": "Port", "value": 1, "modifiable": True},
              {"label": "Direction", "value": 1, "modifiable": True},
              {"label": "Speed", "value": 50, "modifiable": True}],

    "Servo": [{"label": "Port", "value": 1, "modifiable": True},
              {"label": "Angle", "value": 0, "modifiable": True}],

    "Nine axis sensor": [{"label": "Accelerometer", "value": 0, "modifiable": False},
                         {"label": "Gyroscope", "value": 0, "modifiable": False},
                         {"label": "Magnetic", "value": 0, "modifiable": False}],

    "Color sensor": [{"label": "Color_sensor_red", "value": 0, "modifiable": False},
                     {"label": "Color_sensor_green", "value": 0, "modifiable": False},
                     {"label": "Color_sensor_blue", "value": 0, "modifiable": False}],

    "Temperature and humidity": [{"label": "Temperature", "value": 0, "modifiable": False},
                                 {"label": "Humidity", "value": 0, "modifiable": False}],

    "BLE": [{"label": "Is_connected", "value": False, "modifiable": False}]
}
# 定义不同按钮的范围（可以扩展）
value_ranges = {
    "port": (0, 9),
    "red": (0, 255),
    "green": (0, 255),
    "blue": (0, 255),
    "frequency": (20, 20000),
    "song_num": (0, 1),
    "wait_time_ms": (100, 1000),
    "duty": (200, 700),
    "direction": (-1, 1),
    "speed": (0, 100),
    "angle": (0, 360),
    "other": (0, 100)
}

rgb = neopixel.NeoPixel(machine.Pin(38), 10)
pot = ADC(Pin(11))
pot.atten(ADC.ATTN_11DB)    # 衰减设置范围：输入电压0-3.3v
pot.width(ADC.WIDTH_12BIT)  # 读取的电压转为0-4096；ADC.WIDTH_9BIT：0-511
BUTTON_OK = 1      # 确认
BUTTON_RETURN = 2  # 返回
BUTTON_UP = 3      # 上键
BUTTON_DOWN = 4    # 下键
BUTTON_LEFT = 5    # 左键
BUTTON_RIGHT = 6   # 右键
E7 = 2637
G7 = 3136
C7 = 2093
D7 = 2349
F7 = 2794
jingle = [E7, E7, E7, 0,
          E7, E7, E7, 0,
          E7, G7, C7, D7, E7, 0,
          F7, F7, F7, F7, F7, E7, E7, E7, E7, D7, D7, E7, D7, 0, G7, 0,
          E7, E7, E7, 0,
          E7, E7, E7, 0,
          E7, G7, C7, D7, E7, 0,
          F7, F7, F7, F7, F7, E7, E7, E7, G7, G7, F7, D7, C7, 0]


# 获取按钮电压并转换为按钮值
def get_button_ADC():
    pot_value = pot.read()  # 读取ADC值
    time.sleep(0.01)
    VCC = pot_value / 4096 * 3.3  # 将ADC值转换为电压
    # 定义电压范围和对应按钮值的映射
    voltage_to_button = {
        (0.5, 0.7): 2,
        (1.2, 1.4): 3,
        (1.6, 1.7): 4,
        (1.8, 2.1): 5,
        (2.1, 2.4): 6,
    }
    # 遍历字典，判断电压在哪个范围内
    for (low, high), button_value in voltage_to_button.items():
        if low < VCC < high:
            return button_value
    if VCC == 0:
        return 1
    return 0

