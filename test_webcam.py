import time

import cv2


def test_webcam():
    print("Testing webcam access...")

    # Try different backends
    backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]  # macOS backend

    for backend in backends:
        print(f"\nTrying backend: {backend}")
        cap = cv2.VideoCapture(0, backend)

        if not cap.isOpened():
            print(f"Failed to open webcam with backend {backend}")
            continue

        print("Webcam opened successfully")

        # Add a small delay after opening
        time.sleep(1)

        # Try to set resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print(
            f"Resolution set to: {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}"
        )

        # Try multiple frame reads
        print("Attempting to read frames...")
        for i in range(3):
            print(f"Attempt {i+1}...")
            ret, frame = cap.read()

            if not ret or frame is None:
                print(f"Failed to read frame on attempt {i+1}")
                time.sleep(0.5)  # Wait between attempts
            else:
                print(f"Successfully read frame with shape: {frame.shape}")
                # Save the frame to verify it works
                cv2.imwrite(f"test_frame_{backend}_{i}.jpg", frame)
                print(f"Saved test frame to test_frame_{backend}_{i}.jpg")
                break

        # Release the camera
        cap.release()
        print("Webcam released")

        if ret and frame is not None:
            print(f"Successfully captured frame with backend {backend}")
            return True

    return False


if __name__ == "__main__":
    success = test_webcam()
    print(f"\nTest completed with {'success' if success else 'failure'}")
