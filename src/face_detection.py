import cv2

cascade_path = cv2.data.haarcascades
face_cascade = cv2.CascadeClassifier(cascade_path + 'haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier(cascade_path + 'haarcascade_eye.xml') 

# set VideoCapture parameter to 0 should use default local computer webcam
# TODO: need to feed logitech webcam live image instead of local computer webcam
live_capture = cv2.VideoCapture(0)

while 1:
    ret, img = live_capture.read()

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    # draw rectangle around face
    for (x, y, w, h) in faces:
        cv2.rectangle(img, (x, y),(x + w, y + h), (255, 255, 0), 2) 
        roi_gray = gray[y : y + h, x : x + w]
        roi_color = img[y : y + h, x : x + w]

        eyes = eye_cascade.detectMultiScale(roi_gray) 

        # draw a rectangle in eyes
        for (ex, ey, ew, eh) in eyes:
            cv2.rectangle(roi_color, (ex,ey), (ex + ew, ey + eh), (0, 127, 255), 2)

    cv2.imshow('img', img)

    # wait for Esc key to stop
    k = cv2.waitKey(30) & 0xff
    if k == 27:
        break

live_capture.release()
cv2.destroyAllWindows()