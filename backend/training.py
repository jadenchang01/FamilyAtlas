import os
import pickle
from imageClassifier import ImageClassifier

# Point to your labeled training folders
TRAINING_DIR = '/Users/jang-inhwa/Desktop/Training'
CATEGORIES = ['food', 'people', 'scenery', 'others']

training_images = []
labels = []

# Label the training images
for category in CATEGORIES:
    folder = os.path.join(TRAINING_DIR, category)
    for filename in os.listdir(folder):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            full_path = os.path.join(folder, filename)
            training_images.append(full_path)
            labels.append(category)

# Train
classifier = ImageClassifier()
classifier.train(training_images, labels)

# Save
with open('classifier.pkl', 'wb') as f:
    pickle.dump(classifier, f)

print(f"Trained on {len(training_images)} images. Model saved.")