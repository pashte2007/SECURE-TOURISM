import os
import base64
import time
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify, url_for
from twilio.rest import Client
from sklearn.svm import OneClassSVM

app = Flask(__name__)


TWILIO_SID = 'sid'          
TWILIO_AUTH_TOKEN = 'auth_token'   
TWILIO_WHATSAPP_FROM = 'from ' 
USER_WHATSAPP_NUMBER = 'to' 


SAFE_LAT = 18.4575

SAFE_LONG = 73.8508

# Initialize Twilio Client
client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

# Ensure static folder exists for panic button images
if not os.path.exists('static'):
    os.makedirs('static')


# 2. TRAIN AI MODEL (Run on Startup)

print("--- SYSTEM STARTUP ---")
print(f"Training AI Model for Safe Zone: {SAFE_LAT}, {SAFE_LONG}")
train_data = {
    'lat': np.random.normal(SAFE_LAT, 0.01, 500),
    'long': np.random.normal(SAFE_LONG, 0.01, 500)
}
df_train = pd.DataFrame(train_data)
model = OneClassSVM(nu=0.05, kernel="rbf", gamma=100)
model.fit(df_train)
print("✅ AI Model Trained successfully.\n")

last_alert_time = 0


# 3. ROUTES (PAGES)

@app.route('/')
def home():
    """Home Page"""
    return render_template('index.html')

@app.route('/map')
def safety_map():
    #Control map
    return render_template('safety_map.html')

@app.route('/panic')
def panic_button():
    #panic button
    return render_template('panic.html')

@app.route('/ai_guard')
def ai_guard():
    #AI Guard Page
    return render_template('ai_guard.html')


# 4. API ENDPOINTS (BACKEND LOGIC)


# --- Logic for Feature 2: Panic Button ---
@app.route('/send_panic_alert', methods=['POST'])
def send_panic_alert():
    print("⚠️ Panic Alert triggered!")
    data = request.json
    lat = data.get('latitude')
    long = data.get('longitude')
    image_data = data.get('image')

    if not lat or not image_data:
        return jsonify({"status": "error", "message": "Missing GPS or Image"}), 400

    try:
        # Save Image
        header, encoded = image_data.split(",", 1)
        binary_data = base64.b64decode(encoded)
        filename = f"evidence_{int(time.time())}.jpg"
        filepath = os.path.join('static', filename)
        with open(filepath, "wb") as f:
            f.write(binary_data)
        
        # Generate Public Link (Note: This requires Ngrok or public hosting to work for real)
        image_url = url_for('static', filename=filename, _external=True)
        
        # Send WhatsApp
        maps_link = f"http://maps.google.com/?q={lat},{long}"
        msg_body = f"🚨 *PANIC ALERT* 🚨\n\nI need help!\n📍 *Location:* {maps_link}\n(Photo evidence attached)"

        client.messages.create(
            body=msg_body,
            from_=TWILIO_WHATSAPP_FROM,
            to=USER_WHATSAPP_NUMBER,
            media_url=[image_url]
        )
        return jsonify({"status": "success"})

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- Logic for Feature 3: AI Check ---
@app.route('/check_location', methods=['POST'])
def check_location():
    global last_alert_time
    data = request.json
    lat = data['lat']
    long = data['long']
    
    # AI Prediction
    point_df = pd.DataFrame([[lat, long]], columns=['lat', 'long'])
    prediction = model.predict(point_df)[0]
    
    if prediction == 1:
        return jsonify({"status": "SAFE"})
    else:
        # Check cooldown to avoid spamming
        current_time = time.time()
        if (current_time - last_alert_time) > 60: 
            try:
                msg_body = f"🚨 *AI SECURITY ALERT* 🚨\nUser is outside the Safe Zone!\n📍 Location: {lat}, {long}"
                client.messages.create(body=msg_body, from_=TWILIO_WHATSAPP_FROM, to=USER_WHATSAPP_NUMBER)
                last_alert_time = current_time
                print("📲 AI Alert Sent!")
            except Exception as e:
                print(f"❌ Twilio Error: {e}")
                
        return jsonify({"status": "DANGER"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)