<img width="960" height="1280" alt="image" src="https://github.com/user-attachments/assets/7daad7f4-415a-425a-8b79-8eb5feae5dac" /><img width="1600" height="728" alt="image" src="https://github.com/user-attachments/assets/469adae9-95d3-4ab9-8c56-e6d41e502e36" /># AgriDrone – Crop Monitoring and Leaf Fault Analysis

## About the Project
AgriDrone is a group project that combines a DIY drone with a WiFi camera and a Python-based dashboard to support crop monitoring and leaf image analysis.

The system allows users to upload crop images, view possible leaf abnormalities, and get crop-related guidance through a multilingual chatbot.

## Features
- **Live View:** Displays the drone camera app's view on a laptop dashboard by sharing the mobile screen.
- **Leaf Image Analysis:** Analyses uploaded leaf images using colour-based image processing.
- **Fault Estimation:** Estimates possible abnormal areas and their severity.
- **Scan History:** Stores image analysis results and scan details in an SQLite database.
- **Multilingual Chatbot:** Provides crop-related information in English, Hindi, and Marathi.

## Technologies Used
- Python
- Flask
- NumPy
- Pillow (PIL)
- SQLite
- HTML, CSS, and JavaScript
- JSON

## Project Screenshots

### Dashboard
<img width="1600" height="728" alt="image" src="https://github.com/user-attachments/assets/148187b9-a259-43e5-a0ba-0af03415208d" />

### Drone Hardware
<img width="960" height="1280" alt="image" src="https://github.com/user-attachments/assets/b5bfb321-6c2f-4560-9077-1e68f9196f7d" />

### Crop Image Analysis
<img width="1600" height="726" alt="image" src="https://github.com/user-attachments/assets/615b4c4b-71a6-44c7-9031-a1467f241b5c" />


## How It Works
1. The drone camera provides a view of the crops.
2. The mobile camera app's screen is shared with the laptop dashboard.
3. The user uploads a crop or leaf image for analysis.
4. The system checks image colours to identify possible abnormalities.
5. The user can view the analysis and request crop-related guidance from the chatbot.

## Current Limitations
- Automatic image capture and analysis directly from the live camera feed are not yet working.
- Image analysis is based on colour patterns and does not confirm a specific plant disease.
- The chatbot uses predefined responses from a knowledge base.

## Future Improvements
- Integrate automatic image capture and analysis from the live camera feed.
- Train or integrate a machine-learning model for more reliable crop fault detection.
- Improve crop recommendations and chatbot responses.

## Team Project
Developed collaboratively as an academic project.

## Note
This project is a prototype intended to support crop monitoring and identify possible leaf abnormalities. Its results should not be treated as a confirmed plant disease diagnosis.
