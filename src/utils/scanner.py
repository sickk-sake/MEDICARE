import cv2
import numpy as np
from pyzbar.pyzbar import decode
import logging
import time

logger = logging.getLogger(__name__)

class BarcodeScanner:
    """Barcode scanning functionality using OpenCV and pyzbar"""
    
    def __init__(self):
        """Initialize the barcode scanner"""
        self.last_scan_time = 0
        self.last_barcode = None
        
        logger.debug("Barcode scanner initialized")
    
    def scan_image(self, image):
        """
        Scan an image for barcodes
        
        Args:
            image: numpy array image (BGR or RGB format)
            
        Returns:
            List of detected barcode values
        """
        try:
            # Perform barcode detection
            barcodes = decode(image)
            
            # Extract barcode values
            result = []
            for barcode in barcodes:
                # Convert barcode data to string
                barcode_data = barcode.data.decode('utf-8')
                barcode_type = barcode.type
                
                logger.debug(f"Detected {barcode_type} barcode: {barcode_data}")
                
                # Draw rectangle around barcode (for visualization)
                points = barcode.polygon
                if len(points) > 4:
                    hull = cv2.convexHull(np.array([point for point in points], dtype=np.float32))
                    hull = cv2.approxPolyDP(hull, 0.02 * cv2.arcLength(hull, True), True)
                    points = hull
                
                # Add to results
                result.append(barcode_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error scanning barcode: {e}")
            return []
    
    def start_camera_scanning(self, camera_id=0):
        """
        Start continuous barcode scanning from camera
        
        Args:
            camera_id: Camera device ID (default: 0)
            
        Returns:
            OpenCV VideoCapture object
        """
        try:
            # Initialize the camera
            cap = cv2.VideoCapture(camera_id)
            
            if not cap.isOpened():
                raise Exception(f"Could not open camera {camera_id}")
            
            logger.debug(f"Camera {camera_id} initialized successfully")
            return cap
            
        except Exception as e:
            logger.error(f"Error initializing camera: {e}")
            return None
    
    def process_camera_frame(self, frame):
        """
        Process a single camera frame for barcode detection
        
        Args:
            frame: numpy array image from camera
            
        Returns:
            Tuple of (processed_frame, detected_barcodes)
        """
        try:
            # Process at most once every 0.5 seconds to avoid unnecessary CPU usage
            current_time = time.time()
            if current_time - self.last_scan_time < 0.5:
                return frame, []
            
            self.last_scan_time = current_time
            
            # Convert to grayscale for better barcode detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Apply some blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Detect barcodes
            barcodes = decode(blurred)
            
            # Draw bounding boxes and barcode values
            for barcode in barcodes:
                # Extract barcode info
                barcode_data = barcode.data.decode('utf-8')
                barcode_type = barcode.type
                
                # Get bounding box coordinates
                (x, y, w, h) = barcode.rect
                
                # Draw rectangle and text
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                text = f"{barcode_type}: {barcode_data}"
                cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 255, 0), 2)
            
            # Extract barcode values
            barcode_values = [b.data.decode('utf-8') for b in barcodes]
            
            return frame, barcode_values
            
        except Exception as e:
            logger.error(f"Error processing camera frame: {e}")
            return frame, []
    
    def scan_from_image_file(self, image_path):
        """
        Scan barcodes from an image file
        
        Args:
            image_path: Path to image file
            
        Returns:
            List of detected barcode values
        """
        try:
            # Read image
            image = cv2.imread(image_path)
            
            if image is None:
                raise Exception(f"Could not read image from {image_path}")
            
            # Scan for barcodes
            return self.scan_image(image)
            
        except Exception as e:
            logger.error(f"Error scanning from image file: {e}")
            return []
