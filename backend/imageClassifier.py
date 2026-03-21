from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
import cv2
import numpy as np
from pathlib import Path

class ImageClassifier:
    def __init__(self):
        # we will use LDA to classify images
        self.model = LinearDiscriminantAnalysis()
    

    def extract_features(self, image_path):
        """Extract features used for classification"""
        img = cv2.imread(image_path)
        
        # Color features
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h_mean = hsv[:,:,0].mean()
        s_mean = hsv[:,:,1].mean()
        v_mean = hsv[:,:,2].mean()
        
        # Edge features
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.count_nonzero(edges) / edges.size
        
        # Texture
        texture = gray.std()
        
        # Brightness
        brightness = gray.mean()
        
        return np.array([h_mean, s_mean, v_mean, edge_density, texture, brightness])
    

    def train(self, training_images, labels):
        """Train on manually labeled images"""
        features = []
        for img_path in training_images:
            features.append(self.extract_features(img_path))
        
        X = np.array(features)
        y = np.array(labels)
        
        self.model.fit(X, y)
        print("✓ Model trained!")
    
    
    def predict(self, image_path):
        """Predict category of a new image"""
        features = self.extract_features(image_path)
        category = self.model.predict([features])[0]
        return category
