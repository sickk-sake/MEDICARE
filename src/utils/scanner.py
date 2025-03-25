import cv2
from pyzbar.pyzbar import decode
import logging

class BarcodeScanner:
    """
    A class to handle barcode scanning functionality using OpenCV and Pyzbar.
    """
    def __init__(self):
        """Initialize the BarcodeScanner."""
        self.cap = None
        self.logger = logging.getLogger(__name__)

    def start_camera(self, camera_index=0):
        """
        Start the camera for barcode scanning.
        
        Args:
            camera_index (int): Index of the camera to use (default: 0)
            
        Returns:
            bool: True if camera started successfully, False otherwise
        """
        try:
            self.cap = cv2.VideoCapture(camera_index)
            if not self.cap.isOpened():
                self.logger.error("Failed to open camera")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error starting camera: {str(e)}")
            return False

    def stop_camera(self):
        """
        Stop the camera.
        """
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None

    def scan_frame(self, frame):
        """
        Scan a single frame for barcodes.
        
        Args:
            frame: OpenCV image frame to scan
            
        Returns:
            list: Decoded barcode data (empty list if none found)
        """
        try:
            decoded_objects = decode(frame)
            results = []
            
            for obj in decoded_objects:
                barcode_data = obj.data.decode('utf-8')
                barcode_type = obj.type
                results.append({
                    'data': barcode_data,
                    'type': barcode_type,
                })
                
                # Draw a rectangle around the barcode
                points = obj.polygon
                if len(points) > 4:
                    hull = cv2.convexHull(np.array([point for point in points], dtype=np.float32))
                    cv2.polylines(frame, [hull], True, (0, 255, 0), 2)
                else:
                    pts = np.array([point for point in points], dtype=np.int32)
                    cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
                
                # Put the barcode data on the image
                cv2.putText(frame, barcode_data, (obj.rect.left, obj.rect.top - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
            return results, frame
        except Exception as e:
            self.logger.error(f"Error scanning frame: {str(e)}")
            return [], frame

    def scan_barcode(self):
        """
        Continuously scan for barcodes until one is found or cancelled.
        
        Returns:
            dict: Barcode information or None if cancelled/error
        """
        if not self.cap or not self.cap.isOpened():
            if not self.start_camera():
                return None
                
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    self.logger.error("Failed to capture frame")
                    break
                    
                # Mirror the frame for more intuitive user experience
                frame = cv2.flip(frame, 1)
                
                results, processed_frame = self.scan_frame(frame)
                
                cv2.imshow('Barcode Scanner', processed_frame)
                
                # If a barcode is found, return the first one
                if results:
                    cv2.destroyAllWindows()
                    self.stop_camera()
                    return results[0]
                    
                # Break loop with 'q'
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
            cv2.destroyAllWindows()
            self.stop_camera()
            return None
            
        except Exception as e:
            self.logger.error(f"Error in barcode scanning: {str(e)}")
            if self.cap and self.cap.isOpened():
                self.stop_camera()
            cv2.destroyAllWindows()
            return None

    def scan_from_image(self, image_path):
        """
        Scan a barcode from an image file.
        
        Args:
            image_path (str): Path to the image file
            
        Returns:
            dict: Barcode information or None if not found/error
        """
        try:
            # Read the image
            image = cv2.imread(image_path)
            if image is None:
                self.logger.error(f"Failed to load image: {image_path}")
                return None
                
            # Decode barcodes
            decoded_objects = decode(image)
            
            if not decoded_objects:
                return None
                
            # Return the first barcode found
            barcode = decoded_objects[0]
            return {
                'data': barcode.data.decode('utf-8'),
                'type': barcode.type
            }
            
        except Exception as e:
            self.logger.error(f"Error scanning image: {str(e)}")
            return None


if __name__ == "__main__":
    # Simple test of the barcode scanner
    import numpy as np
    logging.basicConfig(level=logging.INFO)
    scanner = BarcodeScanner()
    result = scanner.scan_barcode()
    if result:
        print(f"Barcode detected: {result['data']} ({result['type']})")
    else:
        print("No barcode detected or scanning was cancelled.")
