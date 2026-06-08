import cv2

url = "http://192.168.100.249:4747/video"

cap = cv2.VideoCapture(url)

print("Opened:", cap.isOpened())

ret, frame = cap.read()

print("Read:", ret)
print("Frame:", frame is not None)

cap.release()