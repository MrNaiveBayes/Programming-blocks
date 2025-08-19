from machine import Pin, SPI
from button import *
import lvgl_esp32
import lvgl as lv
import bluetooth
import zc_drive
import _thread
import random
import time
import math

# 初始化 SPI 和显示
try:
    spi = SPI(2, baudrate=80_000_000, sck=Pin(7, Pin.OUT), mosi=Pin(6, Pin.OUT), miso=None)
    display = lvgl_esp32.Display(spi=spi, width=240, height=320, swap_xy=False, mirror_x=True, mirror_y=True,
                                 invert=True, bgr=True, reset=48, dc=4, cs=5, pixel_clock=20_000_000, )
    bl = Pin(1, Pin.OUT)
    bl.on()
    display.init()
    wrapper = lvgl_esp32.Wrapper(display)
    wrapper.init()

except Exception as e:
    print("显示初始化失败:", e)
    raise

# 全局变量
screens = []  # 存储所有主屏幕和子屏幕
current_menu = "main"  # 当前界面类型 ("main" 或 "sub")
current_index = 0  # 当前选中的按钮索引
editing_mode = False  # 是否处于编辑模式
# main_menu_buttons = None  # 主屏幕的按钮列表
sub_menu_buttons = None  # 子屏幕的按钮列表
current_sub_screen_name = None  # 当前子屏幕名称
state_flag = 1  # 确认设备是否正常
refresh_thread = None  # 用于定期刷新数据的线程
refresh_flag = False  # 控制线程运行的标志
sensor_labels = []  # 用于存储传感器显示标签的列表
white_balance_calibration = False  # 白平衡校准
# 黑色字体
style_black_text = lv.style_t()
style_black_text.init()
style_black_text.set_text_color(lv.color_hex(0x000000))
# 白色字体
style_white_text = lv.style_t()
style_white_text.init()
style_white_text.set_text_color(lv.color_hex(0xFFFFFF))


# 更新指针指向的按钮（新增处理空按钮列表的逻辑）
def update_pointer(btn_list, index):
    if not btn_list:  # 如果没有按钮，则直接返回
        return
    for i, btn in enumerate(btn_list):
        if i == index:
            btn.set_style_bg_color(lv.color_hex(0xFF0000), 0)  # 红色背景
        else:
            btn.set_style_bg_color(lv.color_hex(0x87CEFA), 0)  # 淡蓝色背景


# 每过一秒实时更新数据
def update_sensor_data():
    global sensor_labels, refresh_flag
    while refresh_flag:
        if current_sub_screen_name in ["Nine axis sensor", "Color sensor", "Temperature and humidity"]:
            for lbl, item in sensor_labels:
                value = getvalue(item["label"])
                lbl.set_text(f"{item['label']}: {value}")
                lv.task_handler()
        time.sleep(1)


# 创建主屏幕
def create_main_screen():
    global screens
    main_screen = lv.obj()
    btn_list = []
    for i, label in enumerate(main_menu_items):
        btn = lv.button(main_screen)
        btn.set_size(220, 30)
        btn.align(lv.ALIGN.TOP_LEFT, 10, 10 + i * 38)
        lbl = lv.label(btn)
        lbl.set_text(label)
        lbl.add_style(style_black_text, 0)
        btn_list.append(btn)
    screens.append(main_screen)
    return btn_list


# 创建子屏幕
def create_sub_screen(name):
    global screens, refresh_flag, refresh_thread, sensor_labels
    sub_screen = lv.obj()
    btn_list = []
    sensor_labels = []  # 清空传感器标签列表
    # 显示子屏幕标题
    label_title = lv.label(sub_screen)
    label_title.set_text(f"{name} Settings")
    label_title.align(lv.ALIGN.TOP_LEFT, 10, 10)
    # 获取当前子菜单数据
    menu_items = sub_menu_data[name]

    if name == "BLE":
        # 显示蓝牙连接状态
        status_label = lv.label(sub_screen)
        status_label.set_text("Status: Connecting...")
        status_label.align(lv.ALIGN.TOP_LEFT, 10, 50)
        status_label.add_style(style_black_text, 0)
        time.sleep(1)
        BLE.start_connecting()

    # 判断是否需要使用按钮或文本文档
    elif name in ["Nine axis sensor", "Color sensor", "Temperature and humidity"]:
        # 使用文本文档显示
        for i, item in enumerate(menu_items):
            lbl = lv.label(sub_screen)
            value = getvalue(item["label"])  # 动态获取值
            lbl.set_text(f"{item['label']}: {value}")
            lbl.align(lv.ALIGN.TOP_LEFT, 10, 40 + i * 30)
            lbl.add_style(style_black_text, 0)
            sensor_labels.append((lbl, item))

        # 启动数据刷新线程
        refresh_flag = True
        refresh_thread = _thread.start_new_thread(update_sensor_data, ())

    else:
        # 使用按钮显示
        for i, item in enumerate(menu_items):
            btn = lv.button(sub_screen)
            btn.set_size(220, 30)
            btn.align(lv.ALIGN.TOP_LEFT, 10, 40 + i * 38)
            lbl = lv.label(btn)
            # 如果为不可修改值，动态获取数值
            if not item["modifiable"]:
                item["value"] = getvalue(item["label"])
            lbl.set_text(f"{item['label']}: {item['value']}")
            lbl.add_style(style_black_text, 0)
            btn_list.append((btn, lbl, item))  # 按钮、标签、数据

        # 添加 Send 按钮到底部
        if name in ["LED", "Buzzer", "Motor", "Servo"]:
            send_btn = lv.button(sub_screen)
            send_btn.set_size(220, 30)
            send_btn.align(lv.ALIGN.TOP_LEFT, 10, 40 + len(menu_items) * 38)
            lbl_send = lv.label(send_btn)
            lbl_send.set_text("Send")
            lbl_send.add_style(style_black_text, 0)
            btn_list.append((send_btn, lbl_send, None))

    screens.append(sub_screen)
    return btn_list


# 创建文本屏幕
def create_screen(message, set_x=-1, set_y=-1, font_size=1, font_color=0x000000):
    screen = lv.obj()
    label = lv.label(screen)
    label.set_text(message)
    if set_x == -1 or set_y == -1:
        label.align(lv.ALIGN.CENTER, 0, 0)
    else:
        label.set_pos(set_x, set_y)
    style = lv.style_t()
    style.init()
    font = lv.font_montserrat_16  # 默认字体
    if font_size == 1:
        font = lv.font_montserrat_14
    elif font_size == 2:
        font = lv.font_montserrat_16
    elif font_size == 3:
        font = lv.font_montserrat_24
    style.set_text_font(font)
    style.set_text_color(lv.color_hex(font_color))
    label.add_style(style, 0)
    return screen


# 模拟发送数值的函数
def send_value(sub_menu_items, current_screen_name):
    if current_screen_name == 'LED':
        led_port = sub_menu_items[0]['value']
        led_red = sub_menu_items[1]['value']
        led_green = sub_menu_items[2]['value']
        led_blue = sub_menu_items[3]['value']
        led_brightness = sub_menu_items[4]['value']
        rgb[led_port] = (led_red, led_green, led_blue)
        rgb.write()
    elif current_screen_name == 'Motor':
        motor_port = sub_menu_items[0]['value']
        motor_direction = sub_menu_items[1]['value']
        motor_speed = sub_menu_items[2]['value']
        zc_drive.start_motor(motor_port, motor_speed * motor_direction)
    elif current_screen_name == 'Servo':
        servo_port = sub_menu_items[0]['value']
        servo_angle = sub_menu_items[1]['value']
        zc_drive.servo_angle(servo_angle)
    elif current_screen_name == 'Buzzer':
        buzzer_port1 = sub_menu_items[0]['value']
        buzzer_freq1 = sub_menu_items[1]['value']
        buzzer_song1 = sub_menu_items[2]['value']
        buzzer_time1 = sub_menu_items[3]['value']
        buzzer_duty1 = sub_menu_items[4]['value']
        if buzzer_song1 == 1:
            melodies = jingle
            zc_drive.buzzer_play(buzzer_port1, melodies, buzzer_time1, buzzer_duty1)
        else:
            zc_drive.buzzer_start(buzzer_port1, buzzer_freq1, 512)
            time.sleep(1)
            zc_drive.buzzer_stop(buzzer_port1)
            time.sleep(1)


# 获取非可修改数据的值
def getvalue(label):
    global state_flag, refresh_flag, white_balance_calibration
    # 定义数据处理映射表
    sensor_data_mapping = {
        "Accelerometer": lambda data: (data[1], data[2], data[3]),
        "Gyroscope": lambda data: (data[3], data[4], data[5]),
        "Magnetic": lambda data: (data[6], data[7], data[8]),
    }
    color_sensor_mapping = {
        "Color_sensor_red": 1,
        "Color_sensor_green": 2,
        "Color_sensor_blue": 3,
    }

    # 九轴数据处理
    if label in sensor_data_mapping:
        ret = zc_drive.G_sensor_get_data()
        state_flag = ret[0]
        return sensor_data_mapping[label](ret)
    # 颜色数据处理
    if label in color_sensor_mapping:
        if not white_balance_calibration:
            lv.screen_load(create_screen("In white balance calibration..."))
            lv.task_handler()
            white_balance_calibration = zc_drive.color_sensor_init()
            if white_balance_calibration:
                lv.screen_load(create_screen("calibration success !"))
                lv.task_handler()
                time.sleep(1)
            else:
                lv.screen_load(create_screen("calibration Failed !"))
                lv.task_handler()
                time.sleep(1)
        ret = zc_drive.color_sensor_get_rgb()
        state_flag = ret[0]
        return ret[color_sensor_mapping[label]]
    # 温湿度数据处理
    if label == "Temperature" or label == "Humidity":
        ret = zc_drive.get_temperature_humidity()
        state_flag = ret[0]
        return ret[2] if label == "Temperature" else ret[1]

    if state_flag == 0:
        refresh_flag = False

    return 0


# 处理按钮输入
def handle_buttons():
    global current_menu, current_index, editing_mode, main_menu_buttons, sub_menu_buttons, current_sub_screen_name, refresh_flag

    button_get = get_button_ADC()
    # 判断当前界面是否为文本文档界面
    is_text_only = current_menu == "sub" and current_sub_screen_name in [
        "Nine axis sensor", "Color sensor", "Temperature and humidity", "BLE"
    ]

    # 上键
    if button_get == BUTTON_UP and not editing_mode and not is_text_only:
        current_index = (current_index - 1) % len(main_menu_buttons if current_menu == "main" else sub_menu_buttons)
    # 下键
    elif button_get == BUTTON_DOWN and not editing_mode and not is_text_only:
        current_index = (current_index + 1) % len(main_menu_buttons if current_menu == "main" else sub_menu_buttons)

    # 右键
    elif button_get == BUTTON_RIGHT:
        global state_flag
        # 如果当前界面为主界面
        if current_menu == "main":
            current_menu = "sub"
            current_sub_screen_name = main_menu_items[current_index]
            sub_menu_buttons = create_sub_screen(current_sub_screen_name)
            # 如果获取数值失败
            if state_flag == 0:
                refresh_flag = False
                time.sleep(0.1)
                current_menu = "main"
                lv.screen_load(create_screen("Connecting failed!"))
                lv.task_handler()
                time.sleep(1)
                lv.screen_load(screens[0])
                lv.task_handler()
                current_index = 0
                state_flag = 1
            # 加载子屏幕
            else:
                lv.screen_load(screens[-1])
                lv.task_handler()
                current_index = 0
        # 进入编辑模式
        elif current_menu == "sub" and not is_text_only and sub_menu_buttons[current_index][2] and \
                sub_menu_buttons[current_index][2]["modifiable"]:
            if not editing_mode:
                editing_mode = True
        # 发送数据
        elif current_menu == "sub" and not is_text_only and sub_menu_buttons[current_index][2] is None:
            lv.screen_load(create_screen("Send Success!"))
            lv.task_handler()
            time.sleep(1)
            lv.screen_load(screens[-1])
            lv.task_handler()
            current_index = 0
            send_value(sub_menu_data[current_sub_screen_name], current_sub_screen_name)

    # 左键
    elif button_get == BUTTON_LEFT:
        if current_menu == "sub":
            # 退出编辑模式
            if editing_mode:
                editing_mode = False
                sub_menu_buttons[current_index][1].set_text(
                    f"{sub_menu_buttons[current_index][2]['label']}: {sub_menu_buttons[current_index][2]['value']}")
                sub_menu_buttons[current_index][1].add_style(style_black_text, 0)
            # 返回主屏幕
            else:
                if current_sub_screen_name == "BLE":
                    BLE.stop_connecting()
                refresh_flag = False
                time.sleep(0.1)
                current_menu = "main"
                lv.screen_load(screens[0])
                lv.task_handler()

    # 编辑模式下修改值
    if editing_mode and current_menu == "sub" and not is_text_only:
        current_item = sub_menu_buttons[current_index][2]
        value = current_item["value"]
        label = current_item["label"]
        min_val, max_val = value_ranges.get(label.lower(), value_ranges["other"])
        # 上下键调整值并处理循环
        if button_get == BUTTON_UP:  # 上键增加值
            value = min_val if value >= max_val else value + 1
        elif button_get == BUTTON_DOWN:  # 下键减少值
            value = max_val if value <= min_val else value - 1
        # 更新值
        current_item["value"] = value
        sub_menu_buttons[current_index][1].set_text(f"{label}: {value}")
        sub_menu_buttons[current_index][1].add_style(style_white_text, 0)

    # 更新指针
    if current_menu == "main":
        update_pointer(main_menu_buttons, current_index)
    elif current_menu == "sub" and not is_text_only:
        update_pointer([btn for btn, _, _ in sub_menu_buttons], current_index)


# 初始化主屏幕并加载
main_menu_buttons = create_main_screen()
lv.screen_load(screens[0])
lv.task_handler()

################################蓝牙###################################

# 创建 5x5 按钮点阵
rows, cols = 5, 5
btn_matrix = []
btn_size, spacing = 20, 10
x_start, y_start = 10, 10
bright_color_0 = 0x000000
dark_color_0 = 0xFFFFFF
binary_data = [
    "00000",
    "00000",
    "00000",
    "00000",
    "00000",
]
message_lock = _thread.allocate_lock()
message_queue = []  # 消息队列
# 蜂鸣器演奏
buzzer_flag = False
buzzer_port = 4
buzzer_frequency = 2000
buzzer_wait = 1
buzzer_duty = 0


class ESP32_BLE:
    def __init__(self, name):
        self.name = name
        self.is_connected = False
        self.ble = bluetooth.BLE()
        self.ble.active(False)
        self.ble.config(gap_name=name)

    def register(self):
        service_uuid = bluetooth.UUID('6E400001-B5A3-F393-E0A9-E50E24DCCA9E')
        reader_uuid = bluetooth.UUID('6E400002-B5A3-F393-E0A9-E50E24DCCA9E')
        sender_uuid = bluetooth.UUID('6E400003-B5A3-F393-E0A9-E50E24DCCA9E')
        services = (
            (service_uuid, ((sender_uuid, bluetooth.FLAG_NOTIFY), (reader_uuid, bluetooth.FLAG_WRITE_NO_RESPONSE),)),)
        ((self.tx, self.rx),) = self.ble.gatts_register_services(services)

    def advertiser(self):
        name = bytes(self.name, 'UTF-8')
        adv_data = bytearray([2, 1, 2]) + bytearray((len(name) + 1, 0x09)) + name
        self.ble.gap_advertise(100, adv_data)

    def ble_irq(self, event, data):
        global message_queue
        if event == 1:  # 连接事件
            print("蓝牙已连接")
            self.is_connected = True
            lv.screen_load(create_screen("Status: Connected !"))
            lv.task_handler()
        elif event == 2:  # 断开连接
            print("蓝牙已断开")
            self.is_connected = False
            lv.screen_load(create_screen("Status: Disconnected !"))
            lv.task_handler()
        elif event == 3:  # 数据接收
            BLE_MSG = self.ble.gatts_read(self.rx)
            print("收到消息:", BLE_MSG)
            with message_lock:
                message_queue.append(BLE_MSG)
        else:
            print("未知事件:", event)

    def send(self, data):
        self.ble.gatts_notify(1, self.tx, data)

    def start_connecting(self):
        self.ble.active(True)
        self.register()
        self.advertiser()
        self.ble.irq(self.ble_irq)

    def stop_connecting(self):
        self.ble.active(False)
        self.is_connected = False


# 心跳包
def keepalive():
    global white_balance_calibration
    if not white_balance_calibration:
        try:
            white_balance_calibration = zc_drive.color_sensor_init()
            color_R_G_B = 0x09
        except Exception as error:
            print('White balance calibration failed:', error)
            color_R_G_B = 0x00
    ret1 = zc_drive.get_temperature_humidity()  # 温湿度传感器
    ret2 = zc_drive.G_sensor_get_data()         # 九轴传感器
    ret3 = zc_drive.color_sensor_get_rgb()      # 颜色传感器
    # 加速度
    if ret2[1] > 2048:
        acc_x = 255
    elif ret2[1] < -2048:
        acc_x = 0
    else:
        acc_x = (ret2[1] + 2048)/16

    if ret2[2] > 2048:
        acc_y = 255
    elif ret2[2] < -2048:
        acc_y = 0
    else:
        acc_y = (ret2[2] + 2048)/16

    if ret2[3] > 2048:
        acc_z = 255
    elif ret2[3] < -2048:
        acc_z = 0
    else:
        acc_z = (ret2[3] + 2048)/16

    accelerometer_X = (abs(acc_x-128), int(acc_x), 1)
    accelerometer_Y = (abs(acc_y-128), int(acc_y), 2)
    accelerometer_Z = (abs(acc_z-128), int(acc_z), 3)
    accelerometer_X_Y_Z = [accelerometer_X, accelerometer_Y, accelerometer_Z]
    accelerometer_max = max(accelerometer_X_Y_Z, key=lambda item: item[0])
    # 陀螺仪
    pitch_angle = math.atan2(ret2[4], math.sqrt(ret2[5] ** 2 + ret2[6] ** 2)) * (180 / math.pi)  # 计算俯仰角
    roll_angle = math.atan2(ret2[5], math.sqrt(ret2[4] ** 2 + ret2[6] ** 2)) * (180 / math.pi)  # 计算滚转角
    gyroscope_axes = [(abs(pitch_angle), 1 if pitch_angle > 0 else 2),  # 1, 2 : 前, 后
                      (abs(roll_angle), 4 if roll_angle > 0 else 3)]    # 4, 3 : 右, 左
    gyroscope_max = max(gyroscope_axes, key=lambda item: item[0])
    # 颜色传感器
    color_R = min(ret3[1], 255)
    color_G = min(ret3[2], 255)
    color_B = min(ret3[3], 255)

    if color_R < 50 and color_G < 50 and color_B < 50:
        color_R_G_B = 0x01  # 黑色
    elif color_R > 100 and color_G < 180 and color_B > 100:
        color_R_G_B = 0x02  # 紫色
    elif color_R < 50 and color_G < 100 and color_B > 70:
        color_R_G_B = 0x03  # 蓝色
    elif color_R < 30 and color_G > 70 and color_B > 50:
        color_R_G_B = 0x04  # 青色
    elif color_R < 100 and color_G > 150 and color_B < 100:
        color_R_G_B = 0x05  # 绿色
    elif color_R > 100 and color_G > 70 and color_B < 50:
        color_R_G_B = 0x06  # 黄色
    elif color_R > 100 and color_G < 60 and color_B < 60:
        color_R_G_B = 0x07  # 红色
    elif color_R > 200 and color_G > 200 and color_B > 200:
        color_R_G_B = 0x08  # 白色
    else:
        color_R_G_B = 0x09 if not (color_R == color_G == color_B == 0) else 0x00  # 无匹配或无信号

    # f0 00 00 00 00 01 2c 3c 03 4f 00 00 01 00 00 00 00 00 00 ac
    msg_type = b'\xf0'                                       # byte0 心跳包标识
    button = bytearray([get_button_ADC()])                   # byte1 按钮传感器
    temperature = bytearray([int(ret1[2])])                  # byte2 温度传感器
    humidity = bytearray([int(ret1[1])])                     # byte3 湿度传感器
    Light_intensity = b'\x00'                                # byte4 光线强度
    gyroscope_type = bytearray([int(gyroscope_max[1])])      # byte5 倾斜类型
    gyroscope_angle = bytearray([int(gyroscope_max[0])])     # byte5 倾斜角度数值
    voice = bytearray([random.randint(0, 90)])         # byte7 声音传感器
    accelerometer_type = bytearray([accelerometer_max[2]])   # byte8 加速度类型
    accelerometer_value = bytearray([accelerometer_max[1]])  # byte9 加速度数值
    color = bytearray([color_R_G_B])                         # byte10 颜色代号
    color_red = bytearray([color_R])                         # byte11 颜色的红色值
    color_green = bytearray([color_G])                       # byte12 颜色的绿色值
    color_blue = bytearray([color_B])                        # byte13 颜色的蓝色值
    # byte0 ~ byte13 数据汇总
    data_packet = (msg_type + button + temperature + humidity + Light_intensity + gyroscope_type
                   + gyroscope_angle + voice + accelerometer_type + accelerometer_value + color
                   + color_red + color_green + color_blue)
    reserve = b'\x00\x00\x00\x00\x00'  # byte14 ~ byte18
    checksum_msg = bytearray([(sum(data_packet) + sum(reserve)) & 0xFF])
    state_message = data_packet + reserve + checksum_msg

    return state_message


# 更新点阵矩阵
def update_dot_matrix(binary_pattern, bright_color, dark_color):
    global bright_color_0, dark_color_0, btn_matrix
    bright_color_0 = bright_color
    dark_color_0 = dark_color
    for row in btn_matrix:
        for btn in row:
            btn.delete()
    btn_matrix.clear()
    try:
        screen = lv.obj()
        bg_btn = lv.button(screen)
        bg_btn.set_size(240, 240)
        bg_btn.set_pos(x_start - 10, y_start - 10)
        bg_btn.set_style_bg_color(lv.color_hex(0xCCCCCC), 0)
        bg_btn.move_background()

        for row in range(rows):
            row_buttons = []
            for col in range(cols):
                btn = lv.button(screen)
                btn.set_size(btn_size, btn_size)
                btn.set_pos(x_start + col * (btn_size + spacing), y_start + row * (btn_size + spacing))
                row_buttons.append(btn)
            btn_matrix.append(row_buttons)

        for row, binary_row in enumerate(binary_pattern):
            for col, bit in enumerate(binary_row):
                color = lv.color_hex(bright_color_0 if bit == "1" else dark_color_0)
                btn_matrix[row][col].set_style_bg_color(color, 0)

        lv.screen_load(screen)
        lv.task_handler()
    except Exception as error:
        print("点阵更新失败:", error)


# 主要处理函数
def handle_message(local_msg):
    if not local_msg:
        return
    try:
        message_type = local_msg[0]
        # 灯光设置 & 关闭灯光
        if message_type == 0xF1:
            rgb_port = local_msg[1]
            rgb_red = local_msg[2]
            rgb_green = local_msg[3]
            rgb_blue = local_msg[4]
            if rgb_port == 0xFF:
                for i in range(0, 10):
                    rgb[i] = (rgb_red, rgb_green, rgb_blue)
                    rgb.write()
            else:
                rgb[rgb_port] = (rgb_red, rgb_green, rgb_blue)
                rgb.write()
        elif message_type == 0xF2:
            rgb_port = local_msg[1]
            if rgb_port == 0xFF:
                for i in range(0, 10):
                    rgb[i] = (0, 0, 0)
                    rgb.write()
            else:
                rgb[rgb_port] = (0, 0, 0)
                rgb.write()
        # 屏幕渲染 & 更新屏幕
        elif message_type == 0xF3:
            character_x = local_msg[1]
            character_y = local_msg[2]
            character_size = local_msg[3]
            character_msg = local_msg[4:16]
            character_red = local_msg[16]
            character_green = local_msg[17]
            character_blue = local_msg[18]
            character_text = character_msg.strip()
            character_color = character_red | (character_green << 8) | (character_blue << 16)
            lv.screen_load(create_screen(character_text, character_x, character_y, character_size, character_color))
            lv.task_handler()
        elif message_type == 0xF4:
            lv.screen_load(create_screen("  "))
            lv.task_handler()
        # 点阵显示 & 设置点阵颜色
        elif message_type == 0xF5:
            matrix_port = local_msg[1]
            hex_number_1 = local_msg[2]
            hex_number_2 = local_msg[3]
            hex_number_3 = local_msg[4]
            hex_number_4 = local_msg[5]
            binary_string_1 = f"{hex_number_1:08b}"
            binary_string_2 = f"{hex_number_2:08b}"
            binary_string_3 = f"{hex_number_3:08b}"
            binary_string_4 = f"{hex_number_4:08b}"
            if matrix_port == 0x05:
                global binary_data
                binary_string_all = binary_string_1 + binary_string_2 + binary_string_3 + binary_string_4
                binary_data_0x05 = [
                    binary_string_all[0:5],
                    binary_string_all[5:10],
                    binary_string_all[10:15],
                    binary_string_all[15:20],
                    binary_string_all[20:25],
                ]
                binary_data = binary_data_0x05
                update_dot_matrix(binary_data, bright_color_0, dark_color_0)
        elif message_type == 0xF6:
            global binary_data
            bright_red = local_msg[1]
            bright_green = local_msg[2]
            bright_blue = local_msg[3]
            background_red = local_msg[4]
            background_green = local_msg[5]
            background_blue = local_msg[6]
            bright_light = bright_red | (bright_green << 8) | (bright_blue << 16)
            dark_light = background_red | (background_green << 8) | (background_blue << 16)
            update_dot_matrix(binary_data, bright_light, dark_light)
        # 电机设置 & 停止电机转动 & 设置电机速度
        elif message_type == 0xF7:
            motor_port = local_msg[1]
            motor_speed = local_msg[2]
            motor_direction = local_msg[3]
            if motor_direction == 0x02:
                motor_direction -= 3
            if motor_port == 0xFF:
                for i in range(1, 2):
                    zc_drive.start_motor(i, motor_speed * motor_direction)
            else:
                zc_drive.start_motor(motor_port, motor_speed * motor_direction)
        elif message_type == 0xF8:
            motor_port = local_msg[1]
            if motor_port == 0xFF:
                for i in range(1, 2):
                    zc_drive.start_motor(i, 0)
            else:
                zc_drive.start_motor(motor_port, 0)
        elif message_type == 0xF9:
            motor_direction_M1 = local_msg[1]
            motor_speed_M1 = local_msg[2]
            motor_direction_M2 = local_msg[3]
            motor_speed_M2 = local_msg[4]
            if motor_direction_M1 == 0x02:
                motor_direction_M1 -= 3
            if motor_direction_M2 == 0x02:
                motor_direction_M2 -= 3
            zc_drive.start_motor(1, motor_speed_M1 * motor_direction_M1)
            zc_drive.start_motor(2, motor_speed_M2 * motor_direction_M2)
        # 演奏节拍 & 蜂鸣器静音
        # fa 3c 01 b8 ef
        elif message_type == 0xFA:
            global buzzer_flag, buzzer_frequency, buzzer_wait, buzzer_duty
            buzzer_frequency = local_msg[1] * 30
            buzzer_wait = local_msg[2]
            buzzer_duty = local_msg[3]
            buzzer_flag = True
        elif message_type == 0xFB:
            global buzzer_flag
            buzzer_flag = False
            zc_drive.buzzer_stop(buzzer_port)
        else:
            print("未定义信息，请重试")

    except Exception as error:
        print("处理消息失败:", error)


def buzzer_loop():
    """蜂鸣器线程"""
    global buzzer_flag, buzzer_port, buzzer_frequency, buzzer_wait, buzzer_duty
    while True:
        if buzzer_flag:
            try:
                zc_drive.buzzer_start(buzzer_port, buzzer_frequency, buzzer_duty)
                time.sleep(buzzer_wait/10)
                zc_drive.buzzer_start(buzzer_port, buzzer_frequency, 0)
            except Exception as error:
                print("蜂鸣器启动失败:", error)
        time.sleep(0.5)


def handle_message_loop():
    """处理消息的线程"""
    global message_queue
    while True:
        with message_lock:  # 确保线程安全
            if message_queue:
                msg = message_queue.pop(0)
            else:
                msg = None
        if msg:
            try:
                handle_message(msg)
            except Exception as error:
                print("处理消息失败:", error)
        else:
            time.sleep(0.1)


def keepalive_loop():
    """心跳包线程"""
    while True:
        if BLE.is_connected:
            try:
                BLE.send(keepalive())
            except Exception as error:
                print("发送心跳包失败:", error)
        time.sleep(1)


def button_loop():
    """按键处理线程"""
    while True:
        handle_buttons()
        lv.task_handler()
        time.sleep(0.05)


BLE = ESP32_BLE("编程积木")
_thread.stack_size(8192)
_thread.start_new_thread(button_loop, ())
_thread.start_new_thread(buzzer_loop, ())
_thread.start_new_thread(keepalive_loop, ())
_thread.start_new_thread(handle_message_loop, ())



