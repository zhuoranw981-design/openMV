# 形状测量系统 - OpenMV
# 功能：识别黑色矩形框内的图形，测量尺寸和距离
# 支持：矩形、三角形、圆形

import sensor
import image
import time
import math

# ===============================
# 系统配置参数
# ===============================
# 黑色阈值（用于检测边框和图形）
BLACK_THRESHOLD = (0, 50, -128, 127, -128, 127)

# 图像参数
IMAGE_WIDTH = 320
IMAGE_HEIGHT = 240
CENTER_X = IMAGE_WIDTH // 2
CENTER_Y = IMAGE_HEIGHT // 2

# A4纸实际尺寸（用于校准）
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297

# 校准参数
K = 0  # 距离校准系数
calibrated = False

# ===============================
# 初始化传感器
# ===============================
sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)
sensor.skip_frames(time=2000)
sensor.set_auto_gain(False)
sensor.set_auto_whitebal(False)

clock = time.clock()

# ===============================
# 工具函数
# ===============================
def find_border(img):
    """查找黑色矩形边框"""
    blobs = img.find_blobs([BLACK_THRESHOLD],
                          area_threshold=1000,
                          pixels_threshold=1000,
                          merge=True)
    
    if not blobs:
        return None
    
    # 找到最大的黑色边框（A4纸边框）
    max_blob = None
    max_area = 0
    for b in blobs:
        # 检查是否接近矩形
        if b.w() > 50 and b.h() > 50:
            if b.area() > max_area:
                max_area = b.area()
                max_blob = b
    
    return max_blob

def find_inner_shape(img, border_blob):
    """在边框内部查找黑色图形"""
    # 在边框内部创建ROI（向内收缩10像素避免边框干扰）
    roi_x = border_blob.x() + 15
    roi_y = border_blob.y() + 15
    roi_w = border_blob.w() - 30
    roi_h = border_blob.h() - 30
    
    if roi_w <= 0 or roi_h <= 0:
        return None
    
    blobs = img.find_blobs([BLACK_THRESHOLD],
                          roi=(roi_x, roi_y, roi_w, roi_h),
                          area_threshold=100,
                          pixels_threshold=100,
                          merge=True)
    
    if not blobs:
        return None
    
    # 找到最大的图形
    max_blob = None
    max_area = 0
    for b in blobs:
        if b.area() > max_area:
            max_area = b.area()
            max_blob = b
    
    return max_blob

def recognize_shape(blob):
    """根据色块特征识别形状"""
    w = blob.w()
    h = blob.h()
    area = blob.area()
    density = blob.density()
    
    # 计算宽高比
    ratio = float(w) / h if h > 0 else 0
    
    # 计算矩形度（实际面积与外接矩形面积的比值）
    rect_area = w * h
    solidity = float(area) / rect_area if rect_area > 0 else 0
    
    # 判断形状
    if density > 0.92:
        # 正方形或矩形
        if abs(ratio - 1) < 0.15:
            return '正方形', w, h, solidity
        else:
            return '矩形', w, h, solidity
    elif density > 0.65:
        # 圆形
        return '圆形', w, h, solidity
    elif density > 0.4 and solidity < 0.7:
        # 三角形
        return '三角形', w, h, solidity
    else:
        return None, w, h, solidity

def calculate_distance(blob_width_pixel):
    """根据目标宽度计算距离"""
    if K == 0 or blob_width_pixel == 0:
        return 0
    return K / blob_width_pixel

# ===============================
# 校准函数
# ===============================
def calibrate_k():
    """在1米距离处自动计算K值"""
    global K, calibrated
    
    print("="*40)
    print("开始校准K值")
    print("请将A4纸目标物放置在1米距离处")
    print("等待检测边框...")
    
    # 等待检测到边框
    border = None
    for i in range(50):
        img = sensor.snapshot()
        border = find_border(img)
        if border:
            break
        time.sleep(100)
        img.draw_string(50, 100, "等待边框...", color=(255, 0, 0))
    
    if not border:
        print("未检测到边框，使用默认K值")
        K = 5000  # 默认值
        calibrated = True
        return
    
    # 计算K值：K = 距离(mm) * 目标宽度(像素) / 目标实际宽度(mm)
    # 使用A4纸宽度210mm作为参考
    border_width_pixel = border.w()
    K = 1000 * border_width_pixel / A4_WIDTH_MM  # 1000mm = 1米
    
    print("检测到边框: %d x %d 像素" % (border.w(), border.h()))
    print("计算得到K值: %.2f" % K)
    print("校准完成!")
    print("="*40)
    
    # 显示校准结果并等待3秒
    for i in range(30):
        img = sensor.snapshot()
        img.draw_rectangle(border.rect(), color=(0, 255, 0))
        img.draw_string(30, 80, "校准完成!", color=(0, 255, 0))
        img.draw_string(30, 100, "K = %.2f" % K, color=(0, 255, 0))
        img.draw_string(30, 120, "3秒后开始测量...", color=(0, 255, 0))
        time.sleep(100)
    
    calibrated = True

# ===============================
# 主循环
# ===============================
# 先进行校准
calibrate_k()

print("\n开始测量...")
print("识别到图形时会输出结果")

while True:
    clock.tick()
    img = sensor.snapshot()
    
    # 查找边框
    border = find_border(img)
    
    if not border:
        # 未检测到边框
        img.draw_string(50, 100, "未检测到边框", color=(255, 0, 0))
        continue
    
    # 绘制边框
    img.draw_rectangle(border.rect(), color=(0, 255, 0), thickness=2)
    
    # 在边框内查找图形
    shape_blob = find_inner_shape(img, border)
    
    if not shape_blob:
        # 未检测到图形
        img.draw_string(50, 100, "边框内无图形", color=(255, 0, 0))
        continue
    
    # 识别形状
    shape_type, w, h, solidity = recognize_shape(shape_blob)
    
    if shape_type is None:
        # 无法识别形状
        img.draw_rectangle(shape_blob.rect(), color=(128, 128, 128))
        img.draw_cross(shape_blob.cx(), shape_blob.cy(), size=10, color=(128, 128, 128))
        continue
    
    # 计算实际尺寸（使用边框宽度作为参考）
    border_width_mm = A4_WIDTH_MM
    border_width_pixel = border.w()
    scale = border_width_mm / border_width_pixel  # mm/像素
    
    # 计算距离
    distance = calculate_distance(border_width_pixel)
    
    # 计算图形尺寸
    if shape_type == '圆形':
        diameter = w * scale
        height = 0
    elif shape_type == '正方形':
        width = w * scale
        height = h * scale
    elif shape_type == '矩形':
        width = w * scale
        height = h * scale
    elif shape_type == '三角形':
        width = w * scale
        height = h * scale
    
    # 绘制图形
    colors = {
        '圆形': (255, 0, 0),
        '正方形': (0, 255, 0),
        '矩形': (0, 255, 0),
        '三角形': (0, 0, 255)
    }
    color = colors.get(shape_type, (255, 255, 255))
    
    img.draw_rectangle(shape_blob.rect(), color=color, thickness=2)
    img.draw_cross(shape_blob.cx(), shape_blob.cy(), size=10, color=color)
    
    # 显示结果
    img.draw_string(10, 10, "形状: %s" % shape_type, color=color)
    
    if shape_type == '圆形':
        img.draw_string(10, 25, "直径: %.1fmm" % diameter, color=color)
        print("圆形: 直径=%.1fmm, 距离=%.1fmm" % (diameter, distance))
    elif shape_type == '正方形':
        img.draw_string(10, 25, "边长: %.1fmm" % width, color=color)
        print("正方形: 边长=%.1fmm, 距离=%.1fmm" % (width, distance))
    elif shape_type == '矩形':
        img.draw_string(10, 25, "宽: %.1fmm" % width, color=color)
        img.draw_string(10, 40, "高: %.1fmm" % height, color=color)
        print("矩形: 宽=%.1fmm, 高=%.1fmm, 距离=%.1fmm" % (width, height, distance))
    elif shape_type == '三角形':
        img.draw_string(10, 25, "底: %.1fmm" % width, color=color)
        img.draw_string(10, 40, "高: %.1fmm" % height, color=color)
        print("三角形: 底=%.1fmm, 高=%.1fmm, 距离=%.1fmm" % (width, height, distance))
    
    img.draw_string(10, 55, "距离: %.1fmm" % distance, color=(255, 255, 0))
    
    # 显示FPS
    img.draw_string(IMAGE_WIDTH - 60, 10, "FPS:%.1f" % clock.fps(), color=(255, 255, 255))
    
    time.sleep(50)