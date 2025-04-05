from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import os
import json
import base64
import io
import re
import logging
from PIL import Image
import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'feast_community_kitchen_network'

# Configure MongoDB
app.config["MONGO_URI"] = "mongodb://localhost:27017/feast_db"
mongo = PyMongo(app)

# Configure file uploads
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload size
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png', 'gif'}

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Groq API configuration
GROQ_API_KEY = ""
GROQ_VISION_MODEL = "llama-3.2-90b-vision-preview"
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"

# Shelf-life dictionary (in hours)
food_shelf_life = {
    "rice": 12, "dal": 10, "roti": 8, "curry": 8, "sambar": 10, "idli": 12, "dosa": 10,
    "biryani": 12, "vegetables": 8, "milk": 6, "paneer": 6, "chicken": 12, "fish": 8,
    "egg": 10, "fruit": 6, "salad": 6,
    # Add more general food types
    "pasta": 10, "soup": 12, "bread": 8, "canned soup": 72
}

# Helper function to check if file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Function to encode image in base64 (ensures JPEG format)
def encode_image(image_file):
    try:
        img = Image.open(image_file)

        # Convert to RGB if necessary
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Save as JPEG to a buffer
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")  # Force JPEG format
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

        logger.info(f"Image encoded successfully. Base64 length: {len(encoded)}")
        return encoded
    except Exception as e:
        logger.error(f"Failed to process image: {str(e)}")
        return None

# Function to classify food from image
def classify_food(base64_image):
    if not base64_image:
        logger.error("No image provided for classification")
        return None

    # Check for network connectivity
    try:
        # Try to connect to the Groq API
        logger.info("Sending request to Groq API for food classification")
        
        # Create the request payload
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Identify the food item in this image. Give just the name of the food."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                },
            ],
            "model": GROQ_VISION_MODEL
        }
        
        # Log the request (without the full base64 image)
        logger.info(f"Request to Groq API: {str(payload)[:500]}...")
        
        # Make the API call
        response = requests.post(
            "https://api.groq.co/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=10  # Shorter timeout to fail faster
        )

        # Log the response status
        logger.info(f"Groq API response status: {response.status_code}")
        
        # Check for errors
        if response.status_code != 200:
            logger.error(f"Groq API error: {response.status_code} - {response.text}")
            return None
            
        # Parse the response
        result = response.json()
        logger.info(f"Groq API response: {str(result)[:500]}...")
        
        # Extract the food item name
        if 'choices' in result and len(result['choices']) > 0:
            food_item = result["choices"][0]["message"]["content"].strip().lower()
            logger.info(f"Detected Food Item: {food_item}")
            return food_item
        else:
            logger.error("No choices in Groq API response")
            return None
            
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        logger.error(f"API error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Failed to classify food: {str(e)}")
        return None

# Function to check food quality
def check_food_quality(base64_image):
    if not base64_image:
        return {"is_fresh": False, "confidence": 0, "reason": "No image provided"}

    try:
        # Try to connect to the Groq API
        response = requests.post(
            "https://api.groq.co/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text",
                             "text": "Analyze this food image and determine if the food appears fresh or stale/spoiled. Provide your assessment in JSON format with the following fields: is_fresh (boolean), confidence (percentage as integer), reason (brief explanation)."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                        ],
                    },
                ],
                "model": GROQ_VISION_MODEL
            },
            timeout=10  # Shorter timeout to fail faster
        )

        # Check for errors
        if response.status_code != 200:
            logger.error(f"Groq API error: {response.status_code} - {response.text}")
            return {"is_fresh": True, "confidence": 50, "reason": "Unable to analyze freshness due to API error. Assuming fresh."}
            
        result = response.json()
        result_text = result["choices"][0]["message"]["content"].strip()
        
        # Try to extract JSON from the response
        try:
            # Look for JSON pattern in the response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result_json = json.loads(json_match.group(0))
                logger.info(f"Food quality check result: {result_json}")
                return result_json
            else:
                # If no JSON found, parse the text response
                is_fresh = "spoiled" not in result_text.lower() and "stale" not in result_text.lower()
                return {
                    "is_fresh": is_fresh,
                    "confidence": 70,
                    "reason": result_text[:100]  # Truncate long responses
                }
        except json.JSONDecodeError:
            # If JSON parsing fails, use a simple heuristic
            is_fresh = "fresh" in result_text.lower() and "not spoiled" in result_text.lower()
            return {
                "is_fresh": is_fresh,
                "confidence": 60,
                "reason": "Based on text analysis"
            }
    except Exception as e:
        logger.error(f"Failed to check food quality: {str(e)}")
        # Return a default response assuming the food is fresh when API is unavailable
        return {"is_fresh": True, "confidence": 50, "reason": f"Unable to analyze freshness due to network error: {str(e)}. Assuming fresh."}

# Function to get nutrition information
def get_nutrition(food_item):
    if not food_item:
        return "Error: No food item specified"
    
    # First try to get nutrition from a local database (mock implementation)
    nutrition_db = {
        "rice": {
            "calories": "130 per serving",
            "protein": "2.7 g",
            "carbs": "28 g",
            "fats": "0.3 g",
            "fiber": "0.4 g",
            "serving_size": "100 g",
            "vitamins": ["B1", "B3", "B6"],
            "minerals": ["manganese", "magnesium", "phosphorus"]
        },
        "dal": {
            "calories": "116 per serving",
            "protein": "9 g",
            "carbs": "20 g",
            "fats": "0.4 g",
            "fiber": "8 g",
            "serving_size": "100 g",
            "vitamins": ["B1", "B9"],
            "minerals": ["iron", "potassium", "magnesium"]
        },
        "bread": {
            "calories": "265 per serving",
            "protein": "9 g",
            "carbs": "49 g",
            "fats": "3.2 g",
            "fiber": "2.7 g",
            "serving_size": "100 g",
            "vitamins": ["B1", "B2", "B3"],
            "minerals": ["iron", "sodium", "calcium"]
        },
        "vegetables": {
            "calories": "65 per serving",
            "protein": "2.9 g",
            "carbs": "13 g",
            "fats": "0.3 g",
            "fiber": "4 g",
            "serving_size": "100 g",
            "vitamins": ["A", "C", "K"],
            "minerals": ["potassium", "magnesium", "calcium"]
        },
        "fruit": {
            "calories": "60 per serving",
            "protein": "0.8 g",
            "carbs": "15 g",
            "fats": "0.2 g",
            "fiber": "2.5 g",
            "serving_size": "100 g",
            "vitamins": ["C", "A", "B6"],
            "minerals": ["potassium", "magnesium", "copper"]
        }
    }
    
    # Check if we have the food in our local database
    for key, value in nutrition_db.items():
        if key in food_item.lower():
            logger.info(f"Found nutrition info in local database for {food_item}")
            return json.dumps(value)
    
    # If not in local database, try the Groq API
    prompt = f"""
    Provide detailed nutritional information for {food_item} in JSON format with the following structure:
    {{
        "calories": "X per serving",
        "protein": "X g",
        "carbs": "X g",
        "fats": "X g",
        "fiber": "X g",
        "serving_size": "X g/ml",
        "vitamins": ["vitamin A", "vitamin C", ...],
        "minerals": ["calcium", "iron", ...]
    }}
    """

    try:
        response = requests.post(
            "https://api.groq.co/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "messages": [
                    {"role": "system",
                     "content": "You're a nutritional database expert. Provide accurate, detailed nutrition facts in JSON format only."},
                    {"role": "user", "content": prompt},
                ],
                "model": GROQ_TEXT_MODEL
            },
            timeout=10  # Shorter timeout to fail faster
        )

        # Check for errors
        if response.status_code != 200:
            logger.error(f"Groq API error: {response.status_code} - {response.text}")
            # Return generic nutrition info
            return json.dumps({
                "calories": "100-200 per serving (estimate)",
                "protein": "5-10 g (estimate)",
                "carbs": "15-25 g (estimate)",
                "fats": "2-5 g (estimate)",
                "fiber": "2-4 g (estimate)",
                "serving_size": "100 g",
                "vitamins": ["various vitamins"],
                "minerals": ["various minerals"]
            })
            
        result = response.json()
        nutrition_text = result["choices"][0]["message"]["content"].strip()
        
        # Try to parse the response as JSON to ensure it's valid
        try:
            # Look for JSON pattern in the response
            json_match = re.search(r'\{.*\}', nutrition_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # Validate JSON by parsing it
                json.loads(json_str)
                return json_str
            else:
                return json.dumps({"error": "Could not parse nutrition information"})
        except json.JSONDecodeError:
            # If JSON parsing fails, return the text as is
            return json.dumps({"error": "Failed to parse nutrition info", "text": nutrition_text[:200]})
    except Exception as e:
        logger.error(f"Failed to get nutrition info: {str(e)}")
        # Return generic nutrition info when API is unavailable
        return json.dumps({
            "calories": "100-200 per serving (estimate)",
            "protein": "5-10 g (estimate)",
            "carbs": "15-25 g (estimate)",
            "fats": "2-5 g (estimate)",
            "fiber": "2-4 g (estimate)",
            "serving_size": "100 g",
            "vitamins": ["various vitamins"],
            "minerals": ["various minerals"],
            "note": "This is a generic estimate as the online nutrition database is currently unavailable."
        })

# Function to calculate shelf life
def calculate_shelf_life(food_item, quantity="1 serving"):
    if not food_item:
        return {"days": 0, "hours": 0}
    
    # Extract quantity as a number if possible
    quantity_num = 1
    try:
        quantity_num = int(re.search(r'\d+', quantity).group())
    except (AttributeError, ValueError):
        quantity_num = 1
    
    # Get base shelf life in hours
    base_hours = food_shelf_life.get(food_item.lower(), 24)  # Default to 24 hours
    
    # Adjust based on quantity (larger quantities may spoil faster)
    if quantity_num > 5:
        adjusted_hours = max(base_hours - 2, 4)  # Reduce by 2 hours but minimum 4 hours
    else:
        adjusted_hours = base_hours
    
    return {
        "days": adjusted_hours // 24,
        "hours": adjusted_hours
    }

# Routes
@app.route('/')
def index():
    return render_template('index.html')

# Define user roles
ROLES = {
    'donor': 'Food Donor',
    'kitchen': 'Community Kitchen',
    'volunteer': 'Volunteer',
    'seeker': 'Food Seeker',
    'buyer': 'Food Buyer'
}

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = mongo.db.users
        
        # Check if username already exists
        existing_user = users.find_one({'username': request.form['username']})
        
        if existing_user is None:
            # Hash the password
            hashed_password = generate_password_hash(request.form['password'])
            
            # Create new user
            user_data = {
                'username': request.form['username'],
                'password': hashed_password,
                'email': request.form['email'],
                'role': request.form['role'],
                'created_at': datetime.now()
            }
            
            # Add role-specific fields
            if request.form['role'] == 'donor':
                user_data.update({
                    'name': request.form['name'],
                    'phone': request.form['phone'],
                    'address': request.form['address']
                })
            elif request.form['role'] == 'kitchen':
                user_data.update({
                    'kitchen_name': request.form['kitchen_name'],
                    'contact_person': request.form['contact_person'],
                    'phone': request.form['phone'],
                    'address': request.form['address'],
                    'capacity': request.form['capacity']
                })
            elif request.form['role'] == 'volunteer':
                user_data.update({
                    'name': request.form['name'],
                    'phone': request.form['phone'],
                    'availability': request.form['availability']
                })
            elif request.form['role'] == 'seeker':
                user_data.update({
                    'name': request.form['name'],
                    'phone': request.form['phone'],
                    'address': request.form['address'],
                    'family_size': request.form['family_size']
                })
            elif request.form['role'] == 'buyer':
                user_data.update({
                    'name': request.form['name'],
                    'phone': request.form['phone'],
                    'address': request.form['address'],
                    'preferred_payment': request.form['preferred_payment']
                })
            
            # Insert the user
            users.insert_one(user_data)
            
            # Set session
            session['username'] = request.form['username']
            session['role'] = request.form['role']
            
            # Redirect based on role
            if request.form['role'] == 'donor':
                return redirect(url_for('donor_dashboard'))
            elif request.form['role'] == 'kitchen':
                return redirect(url_for('kitchen_dashboard'))
            elif request.form['role'] == 'volunteer':
                return redirect(url_for('volunteer_dashboard'))
            elif request.form['role'] == 'seeker':
                return redirect(url_for('seeker_dashboard'))
            elif request.form['role'] == 'buyer':
                return redirect(url_for('buyer_dashboard'))
        
        # If user exists
        flash('Username already exists')
        return redirect(url_for('register'))
    
    return render_template('register.html', roles=ROLES)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = mongo.db.users
        
        # Find the user
        login_user = users.find_one({'username': request.form['username']})
        
        if login_user:
            # Check password
            if check_password_hash(login_user['password'], request.form['password']):
                session['username'] = login_user['username']
                session['role'] = login_user['role']
                session['user_id'] = str(login_user['_id'])  # Convert ObjectId to string
                
                # Redirect based on role
                if login_user['role'] == 'donor':
                    return redirect(url_for('donor_dashboard'))
                elif login_user['role'] == 'kitchen':
                    return redirect(url_for('kitchen_dashboard'))
                elif login_user['role'] == 'volunteer':
                    return redirect(url_for('volunteer_dashboard'))
                elif login_user['role'] == 'seeker':
                    return redirect(url_for('seeker_dashboard'))
                elif login_user['role'] == 'buyer':
                    return redirect(url_for('buyer_dashboard'))
            
            # Invalid password
            flash('Invalid username/password combination')
            return redirect(url_for('login'))
        
        # User doesn't exist
        flash('Username not found')
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/donor')
def donor_dashboard():
    if 'username' not in session or session['role'] != 'donor':
        return redirect(url_for('login'))
    
    # Get donor's donations
    donations = list(mongo.db.donations.find({'donor': session['username']}))
    
    return render_template('donor.html', donations=donations)

@app.route('/donate-food', methods=['GET', 'POST'])
def donate_food():
    if 'username' not in session or session['role'] != 'donor':
        flash('Please login as a donor to donate food')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Process donation form submission
        food_name = request.form.get('food_name')
        quantity = request.form.get('quantity')
        expiry_date = request.form.get('expiry_date')
        pickup_address = request.form.get('pickup_address')
        preparation_date = request.form.get('preparation_date', '')
        food_type = request.form.get('food_type', '')
        
        # Handle image upload if present
        food_image_url = None
        if 'food_image' in request.files:
            file = request.files['food_image']
            if file and file.filename != '' and allowed_file(file.filename):
                # Save the file
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                filename = secure_filename(f"{timestamp}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                food_image_url = f"/uploads/{filename}"
                
                # Process the image for food analysis if food name not provided
                if not food_name:
                    base64_image = encode_image(file)
                    detected_food = classify_food(base64_image)
                    if detected_food:
                        food_name = detected_food
                
                # Check food quality
                base64_image = encode_image(file)
                quality_result = check_food_quality(base64_image)
                
                # If food is not fresh, reject the donation
                if quality_result and quality_result.get('is_fresh') is False:
                    flash(f'Food appears to be stale or spoiled: {quality_result.get("reason", "Unknown reason")}')
                    return redirect(url_for('donate_food'))
        
        # Create donation record
        donation = {
            'donor': session['username'],
            'food_name': food_name,
            'food_type': food_type,
            'quantity': quantity,
            'expiry_date': expiry_date,
            'preparation_date': preparation_date,
            'pickup_address': pickup_address,
            'food_image_url': food_image_url,
            'status': 'pending',
            'created_at': datetime.now()
        }
        
        mongo.db.donations.insert_one(donation)
        flash('Food donation registered successfully!')
        return redirect(url_for('donor_dashboard'))
    
    # For GET requests, show the donation form
    return render_template('donate.html')

@app.route('/kitchen')
def kitchen_dashboard():
    if 'username' not in session or session['role'] != 'kitchen':
        return redirect(url_for('login'))
    
    # Get kitchen's inventory
    inventory = list(mongo.db.inventory.find({'kitchen': session['username']}))
    
    # Get kitchen's meal plans
    meal_plans = list(mongo.db.meal_plans.find({'kitchen': session['username']}))
    
    return render_template('kitchen.html', inventory=inventory, meal_plans=meal_plans)

@app.route('/volunteer')
def volunteer_dashboard():
    if 'username' not in session or session['role'] != 'volunteer':
        return redirect(url_for('login'))
    
    # Get available pickups
    pickups = list(mongo.db.pickups.find({'status': 'pending'}))
    
    # Get volunteer's assigned pickups
    my_pickups = list(mongo.db.pickups.find({'volunteer': session['username']}))
    
    return render_template('volunteer.html', pickups=pickups, my_pickups=my_pickups)

@app.route('/seeker')
def seeker_dashboard():
    if 'username' not in session or session['role'] != 'seeker':
        return redirect(url_for('login'))
    
    # Get available meal plans
    meal_plans = list(mongo.db.meal_plans.find({'status': 'available'}))
    
    # Get seeker's requests
    my_requests = list(mongo.db.requests.find({'seeker': session['username']}))
    
    return render_template('seeker.html', meal_plans=meal_plans, my_requests=my_requests)

@app.route('/buyer')
def buyer_dashboard():
    if 'username' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    
    # Get available meal plans
    meal_plans = list(mongo.db.meal_plans.find({'status': 'available'}))
    
    # Get buyer's requests
    my_requests = list(mongo.db.requests.find({'buyer': session['username']}))
    
    return render_template('buyer.html', meal_plans=meal_plans, my_requests=my_requests)

@app.route('/request-food', methods=['GET', 'POST'])
def request_food():
    if 'username' not in session or session['role'] != 'seeker':
        flash('Please login as a food seeker to request food')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Process the food request form
        food_type = request.form.get('food_type')
        servings = request.form.get('servings')
        delivery_address = request.form.get('delivery_address')
        preferred_date = request.form.get('preferred_date')
        special_notes = request.form.get('special_notes', '')
        
        # Get dietary restrictions (returns list if multiple selected, or None if none selected)
        dietary_restrictions = request.form.getlist('dietary_restrictions[]')
        
        # Additional form fields
        preferred_time = request.form.get('preferred_time', '')
        contact_name = request.form.get('contact_name', session.get('name', ''))
        contact_phone = request.form.get('contact_phone', '')
        alternate_contact = request.form.get('alternate_contact', '')
        text_updates = True if request.form.get('text_updates') == 'yes' else False
        
        # For specific items food type
        specific_items = request.form.get('specific_items', '') if food_type == 'specific_items' else ''
        
        # Create food request record
        food_request = {
            'seeker': session['username'],
            'food_type': food_type,
            'specific_items': specific_items,
            'servings': servings,
            'dietary_restrictions': dietary_restrictions,
            'delivery_address': delivery_address,
            'preferred_date': preferred_date,
            'preferred_time': preferred_time,
            'contact_name': contact_name,
            'contact_phone': contact_phone,
            'alternate_contact': alternate_contact,
            'text_updates': text_updates,
            'special_notes': special_notes,
            'status': 'pending',
            'created_at': datetime.now()
        }
        
        # Save to database
        mongo.db.requests.insert_one(food_request)
        
        flash('Food request submitted successfully!')
        return redirect(url_for('seeker_dashboard'))
    
    # For GET requests, show the food request form
    return render_template('request_food.html')

# API for food analysis
@app.route('/api/analyze-food', methods=['POST'])
def analyze_food_api():
    try:
        if 'food_image' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['food_image']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        # Get additional parameters
        prepared_at = request.form.get('prepared_at', datetime.now().strftime('%d-%m-%Y'))
        food_quantity = request.form.get('food_quantity', '1 serving')
        food_name_override = request.form.get('food_name', '')  # Allow manual override
        
        logger.info(f"Processing food image: {file.filename}")
        
        # Process the image
        base64_image = encode_image(file)
        if not base64_image:
            logger.error("Failed to encode image")
            return jsonify({'error': 'Failed to process image'}), 500
        
        logger.info(f"Image encoded successfully, length: {len(base64_image)}")
        
        # Use provided food name if available, otherwise classify from image
        food_name = None
        if food_name_override:
            food_name = food_name_override
            logger.info(f"Using provided food name: {food_name}")
        else:
            # Classify food
            food_name = classify_food(base64_image)
            if not food_name:
                logger.warning("Food classification failed, using generic food type")
                food_name = "food item"  # Fallback to generic food item
        
        logger.info(f"Food classified as: {food_name}")
        
        # Check food quality
        quality_check = check_food_quality(base64_image)
        logger.info(f"Quality check result: {quality_check}")
        
        # Calculate shelf life
        shelf_life = calculate_shelf_life(food_name, food_quantity)
        logger.info(f"Calculated shelf life: {shelf_life}")
        
        # Calculate expiry date
        try:
            # Parse the prepared_at date in dd-mm-yyyy format
            if '-' in prepared_at:
                prepared_date = datetime.strptime(prepared_at, '%d-%m-%Y')
            else:
                # Fallback to current date if format is incorrect
                prepared_date = datetime.now()
                
            expiry_date = prepared_date + timedelta(hours=shelf_life['hours'])
            expiry_date_str = expiry_date.strftime('%d-%m-%Y %H:%M')
        except Exception as e:
            logger.error(f"Error calculating expiry date: {str(e)}")
            expiry_date_str = "Unknown"
        
        # Return the analysis results
        result = {
            'food_name': food_name,
            'quality_check': quality_check,
            'shelf_life_days': shelf_life['days'],
            'shelf_life_hours': shelf_life['hours'],
            'prepared_at': prepared_at,
            'expiry_date': expiry_date_str
        }
        
        logger.info(f"Analysis complete: {result}")
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error in food analysis: {str(e)}")
        return jsonify({'error': str(e)}), 500

# API for nutritional information
@app.route('/api/nutritional-info', methods=['POST'])
def nutritional_info_api():
    try:
        data = request.get_json()
        if not data or 'food_name' not in data:
            return jsonify({'error': 'Food name is required'}), 400
        
        food_name = data['food_name']
        nutrition_info = get_nutrition(food_name)
        
        return jsonify({'nutrition_info': nutrition_info})
    
    except Exception as e:
        logger.error(f"Error getting nutritional info: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route to handle food request cancellation
@app.route('/cancel-request/<request_id>', methods=['POST'])
def cancel_request(request_id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'You must be logged in to cancel a request'}), 401
    
    try:
        # Find the request
        food_request = mongo.db.requests.find_one({'_id': ObjectId(request_id)})
        
        if not food_request:
            return jsonify({'success': False, 'message': 'Request not found'}), 404
        
        # Check if the request belongs to the current user
        if food_request['seeker'] != session['username']:
            return jsonify({'success': False, 'message': 'You can only cancel your own requests'}), 403
        
        # Check if the request is in a cancellable state (pending)
        if food_request['status'] != 'pending':
            return jsonify({'success': False, 'message': 'Only pending requests can be cancelled'}), 400
        
        # Update the request status to cancelled
        mongo.db.requests.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {'status': 'cancelled', 'cancelled_at': datetime.now()}}
        )
        
        return jsonify({'success': True, 'message': 'Request cancelled successfully'})
    
    except Exception as e:
        app.logger.error(f"Error cancelling request: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while cancelling the request'}), 500

# API to get volunteer locations (for map display)
@app.route('/api/volunteers-location', methods=['GET'])
def get_volunteer_locations():
    if 'username' not in session:
        return jsonify([])
    
    try:
        # Get active volunteers with location data
        volunteers = list(mongo.db.users.find(
            {'role': 'volunteer', 'status': 'active'},
            {'_id': 1, 'name': 1, 'location': 1}
        ))
        
        # Convert ObjectId to string for JSON serialization
        for volunteer in volunteers:
            volunteer['_id'] = str(volunteer['_id'])
        
        return jsonify(volunteers)
    
    except Exception as e:
        app.logger.error(f"Error fetching volunteer locations: {str(e)}")
        return jsonify([])

# Serve uploaded files
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/purchase-food', methods=['GET', 'POST'])
def purchase_food():
    if 'username' not in session or session['role'] != 'buyer':
        flash('Please login as a buyer to purchase food')
        return redirect(url_for('login'))
    
    meal_id = request.args.get('meal_id')
    
    if request.method == 'POST':
        # Process purchase form submission
        meal_id = request.form.get('meal_id')
        quantity = request.form.get('quantity')
        pickup_date = request.form.get('pickup_date')
        pickup_time_start = request.form.get('pickup_time_start')
        pickup_time_end = request.form.get('pickup_time_end')
        contact_name = request.form.get('contact_name')
        contact_phone = request.form.get('contact_phone')
        special_instructions = request.form.get('special_instructions', '')
        payment_method = request.form.get('payment_method')
        
        # Get the meal details
        meal = mongo.db.meal_plans.find_one({'_id': ObjectId(meal_id)})
        
        if not meal:
            flash('Food item not found')
            return redirect(url_for('purchase_food'))
        
        # Check if quantity is available
        if int(quantity) > meal.get('available_quantity', 0):
            flash('Requested quantity is not available')
            return redirect(url_for('purchase_food', meal_id=meal_id))
        
        # Calculate total price
        total_price = int(quantity) * meal.get('price', 0)
        
        # Create purchase record
        purchase = {
            'buyer': session['username'],
            'meal_id': ObjectId(meal_id),
            'food_name': meal.get('name'),
            'quantity': quantity,
            'price': total_price,
            'pickup_date': pickup_date,
            'pickup_time_start': pickup_time_start,
            'pickup_time_end': pickup_time_end,
            'contact_name': contact_name,
            'contact_phone': contact_phone,
            'special_instructions': special_instructions,
            'payment_method': payment_method,
            'seller': meal.get('seller', 'Unknown'),
            'pickup_address': meal.get('location', ''),
            'status': 'pending',
            'created_at': datetime.now()
        }
        
        # Insert the purchase record
        mongo.db.purchases.insert_one(purchase)
        
        # Update meal plan available quantity
        new_quantity = meal.get('available_quantity', 0) - int(quantity)
        mongo.db.meal_plans.update_one(
            {'_id': ObjectId(meal_id)},
            {'$set': {'available_quantity': new_quantity}}
        )
        
        flash('Food purchase request submitted successfully!')
        return redirect(url_for('buyer_dashboard'))
    
    # For GET requests
    if meal_id:
        # Show purchase form for specific meal
        meal = mongo.db.meal_plans.find_one({'_id': ObjectId(meal_id)})
        if not meal:
            flash('Food item not found')
            return redirect(url_for('purchase_food'))
        
        return render_template('purchase_food.html', meal=meal)
    else:
        # Show list of available meals
        meal_plans = list(mongo.db.meal_plans.find({'status': 'available', 'available_quantity': {'$gt': 0}}))
        return render_template('purchase_food.html', meal_plans=meal_plans)

@app.route('/cancel-purchase/<purchase_id>', methods=['POST'])
def cancel_purchase(purchase_id):
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'You must be logged in to cancel a purchase'}), 401
    
    try:
        # Find the purchase
        purchase = mongo.db.purchases.find_one({'_id': ObjectId(purchase_id)})
        
        if not purchase:
            return jsonify({'success': False, 'message': 'Purchase not found'}), 404
        
        # Check if user owns this purchase
        if purchase['buyer'] != session['username']:
            return jsonify({'success': False, 'message': 'You can only cancel your own purchases'}), 403
        
        # Check if purchase is in a cancellable state
        if purchase['status'] != 'pending':
            return jsonify({'success': False, 'message': 'Only pending purchases can be cancelled'}), 400
        
        # Update purchase status
        mongo.db.purchases.update_one(
            {'_id': ObjectId(purchase_id)},
            {'$set': {'status': 'cancelled'}}
        )
        
        # Return quantity to meal plan
        mongo.db.meal_plans.update_one(
            {'_id': purchase['meal_id']},
            {'$inc': {'available_quantity': int(purchase['quantity'])}}
        )
        
        return jsonify({'success': True, 'message': 'Purchase cancelled successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
