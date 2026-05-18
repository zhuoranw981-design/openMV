import sensor, image, time

# ===== 摄像头初始化 =====
sensor.reset()
sensor.set_pixformat(sensor.GRAYSCALE)
sensor.set_framesize(sensor.VGA)
sensor.set_windowing((200, 240))
sensor.skip_frames(time=2000)

clock = time.clock()

# ===== 标定参数（黑框 20cm × 29cm）=====
FRAME_W_REAL = 20.0    # cm
FRAME_H_REAL = 29.0    # cm

# ===== 自动标定参数 =====
CALIB_DISTANCE = 1.0   # ✅ 修改为 1 米
calibrated = False
REF_FRAME_W_PIXEL = None

# ===== Blob 工具函数 =====
def find_center_min_blob(blobs):
    blob = None
    min_area = 100000
    for b in blobs:
        if abs(b.cx() - 100) + abs(b.cy() - 120) > 50:
            continue
        if b.area() < min_area:
            min_area = b.area()
            blob = b
    return blob

def find_center_max_blob(blobs):
    blob = None
    max_area = 0
    for b in blobs:
        if abs(b.cx() - 100) + abs(b.cy() - 120) > 50:
            continue
        if b.area() > max_area:
            max_area = b.area()
            blob = b
    return blob

# ===== 全局状态 =====
dist_buf = []

def smooth_distance(d):
    dist_buf.append(d)
    if len(dist_buf) > 5:
        dist_buf.pop(0)
    return sum(dist_buf) / len(dist_buf)

# ===== 主循环 =====
while True:
    clock.tick()
    img = sensor.snapshot()

    frames = img.find_blobs([(150, 255)])
    frame_blob = find_center_min_blob(frames)

    if not frame_blob:
        continue

    # ===== 自动标定（1m 处）=====
    if not calibrated:
        print("正在自动标定 1m 距离...")
        if frame_blob.w() > 30:
            REF_FRAME_W_PIXEL = frame_blob.w()
            calibrated = True
            print("标定完成：")
            print("REF_FRAME_W_PIXEL =", REF_FRAME_W_PIXEL)
        continue

    # ===== ROI =====
    roi_x = frame_blob.x() + 5
    roi_y = frame_blob.y() + 5
    roi_w = frame_blob.w() - 10
    roi_h = frame_blob.h() - 10

    if roi_w <= 0 or roi_h <= 0:
        img.draw_rectangle(frame_blob.rect())
        continue

    roi = (roi_x, roi_y, roi_w, roi_h)

    objs = img.find_blobs([(0, 150)], roi=roi)
    obj_blob = find_center_max_blob(objs)

    # ===== Project 2 =====
    if obj_blob:
        pixel_to_cm = FRAME_W_REAL / frame_blob.w()

        distance = CALIB_DISTANCE * (REF_FRAME_W_PIXEL / frame_blob.w())
        distance = smooth_distance(distance)

        obj_w_cm = obj_blob.w() * pixel_to_cm
        obj_h_cm = obj_blob.h() * pixel_to_cm

        density = obj_blob.density()
        if density > 0.9:
            shape = "矩形"
        elif density > 0.6:
            shape = "圆形"
        elif density > 0.4:
            shape = "三角形"
        else:
            shape = "未知"

        print("Project 2")
        print("形状:", shape)
        print("尺寸: %.2f x %.2f cm" % (obj_w_cm, obj_h_cm))
        print("距离: %.3f m" % distance)

        img.draw_rectangle(frame_blob.rect())
        img.draw_rectangle(obj_blob.rect())
        img.draw_string(10, 10, "W:%.2fcm" % obj_w_cm)
        img.draw_string(10, 20, "D:%.3fm" % distance)

    else:
        img.draw_rectangle(frame_blob.rect())

    # print(clock.fps())