from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from datetime import datetime
import os
import json

app = Flask(__name__)
app.secret_key = 'feast_community_kitchen_network'

# Configure MongoDB
app.config["MONGO_URI"] = "mongodb://localhost:27017/feast_db"
mongo = PyMongo(app)

# User roles
ROLES = {
    'donor': 'Donor',
    'volunteer': 'Volunteer',
    'kitchen': 'Community Kitchen',
    'seeker': 'Food Seeker',
    'admin': 'Administrator'
}

# Routes
@app.route('/')
def index():
    return render_template('index.html')

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = mongo.db.users.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['name'] = user['name']
            session['role'] = user['role']
            
            # Redirect based on role
            if user['role'] == 'volunteer':
                return redirect(url_for('volunteer_dashboard'))
            elif user['role'] == 'kitchen':
                return redirect(url_for('kitchen_dashboard'))
            elif user['role'] == 'seeker':
                return redirect(url_for('seeker_dashboard'))
            elif user['role'] == 'donor':
                return redirect(url_for('donor_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        # Check if email already exists
        if mongo.db.users.find_one({'email': email}):
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        # Create new user
        new_user = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password),
            'role': role,
            'phone': phone,
            'address': address,
            'created_at': datetime.now(),
            'location': {
                'type': 'Point',
                'coordinates': [0, 0]  # Default coordinates, will be updated
            }
        }
        
        user_id = mongo.db.users.insert_one(new_user).inserted_id
        
        # Auto login after registration
        session['user_id'] = str(user_id)
        session['name'] = name
        session['role'] = role
        
        flash('Registration successful!', 'success')
        
        # Redirect based on role
        if role == 'volunteer':
            return redirect(url_for('volunteer_dashboard'))
        elif role == 'kitchen':
            return redirect(url_for('kitchen_dashboard'))
        elif role == 'seeker':
            return redirect(url_for('seeker_dashboard'))
        elif role == 'donor':
            return redirect(url_for('donor_dashboard'))
        else:
            return redirect(url_for('index'))
    
    return render_template('register.html', roles=ROLES)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

# Dashboard routes
@app.route('/volunteer')
def volunteer_dashboard():
    if 'user_id' not in session or session['role'] != 'volunteer':
        flash('Please login as a volunteer', 'warning')
        return redirect(url_for('login'))
    
    # Get assigned tasks
    tasks = list(mongo.db.tasks.find({'volunteer_id': ObjectId(session['user_id'])}))
    
    return render_template('volunteer.html', tasks=tasks)

@app.route('/kitchen')
def kitchen_dashboard():
    if 'user_id' not in session or session['role'] != 'kitchen':
        flash('Please login as a community kitchen', 'warning')
        return redirect(url_for('login'))
    
    # Get kitchen's food inventory
    inventory = list(mongo.db.inventory.find({'kitchen_id': ObjectId(session['user_id'])}))
    
    return render_template('kitchen.html', inventory=inventory)

@app.route('/seeker')
def seeker_dashboard():
    if 'user_id' not in session or session['role'] != 'seeker':
        flash('Please login as a food seeker', 'warning')
        return redirect(url_for('login'))
    
    # Get nearby volunteers and kitchens
    volunteers = list(mongo.db.users.find({'role': 'volunteer'}))
    kitchens = list(mongo.db.users.find({'role': 'kitchen'}))
    
    return render_template('seeker.html', volunteers=volunteers, kitchens=kitchens)

@app.route('/donor')
def donor_dashboard():
    if 'user_id' not in session or session['role'] != 'donor':
        flash('Please login as a donor', 'warning')
        return redirect(url_for('login'))
    
    # Get donor's donation history
    donations = list(mongo.db.donations.find({'donor_id': ObjectId(session['user_id'])}))
    
    return render_template('donor.html', donations=donations)

# API routes for location tracking
@app.route('/api/update-location', methods=['POST'])
def update_location():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    data = request.json
    lat = data.get('latitude')
    lng = data.get('longitude')
    
    if not lat or not lng:
        return jsonify({'status': 'error', 'message': 'Invalid coordinates'}), 400
    
    # Update user location
    mongo.db.users.update_one(
        {'_id': ObjectId(session['user_id'])},
        {'$set': {
            'location': {
                'type': 'Point',
                'coordinates': [float(lng), float(lat)]
            }
        }}
    )
    
    return jsonify({'status': 'success', 'message': 'Location updated'})

@app.route('/api/volunteers-location')
def get_volunteers_location():
    volunteers = list(mongo.db.users.find(
        {'role': 'volunteer'},
        {'_id': 1, 'name': 1, 'location': 1}
    ))
    
    # Convert ObjectId to string for JSON serialization
    for volunteer in volunteers:
        volunteer['_id'] = str(volunteer['_id'])
    
    return jsonify(volunteers)

# Food donation and request routes
@app.route('/donate', methods=['GET', 'POST'])
def donate_food():
    if 'user_id' not in session:
        flash('Please login to donate food', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        food_name = request.form.get('food_name')
        quantity = request.form.get('quantity')
        expiry_date = request.form.get('expiry_date')
        pickup_address = request.form.get('pickup_address')
        
        donation = {
            'donor_id': ObjectId(session['user_id']),
            'food_name': food_name,
            'quantity': quantity,
            'expiry_date': expiry_date,
            'pickup_address': pickup_address,
            'status': 'pending',
            'created_at': datetime.now()
        }
        
        mongo.db.donations.insert_one(donation)
        
        flash('Food donation registered successfully!', 'success')
        return redirect(url_for('donor_dashboard'))
    
    return render_template('donate.html')

@app.route('/request-food', methods=['GET', 'POST'])
def request_food():
    if 'user_id' not in session:
        flash('Please login to request food', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        food_type = request.form.get('food_type')
        servings = request.form.get('servings')
        delivery_address = request.form.get('delivery_address')
        
        food_request = {
            'seeker_id': ObjectId(session['user_id']),
            'food_type': food_type,
            'servings': servings,
            'delivery_address': delivery_address,
            'status': 'pending',
            'created_at': datetime.now()
        }
        
        mongo.db.food_requests.insert_one(food_request)
        
        flash('Food request submitted successfully!', 'success')
        return redirect(url_for('seeker_dashboard'))
    
    return render_template('request_food.html')

# Task assignment for volunteers
@app.route('/assign-task/<volunteer_id>', methods=['POST'])
def assign_task(volunteer_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    data = request.json
    task_type = data.get('task_type')
    description = data.get('description')
    location = data.get('location')
    
    task = {
        'volunteer_id': ObjectId(volunteer_id),
        'task_type': task_type,
        'description': description,
        'location': location,
        'status': 'assigned',
        'created_at': datetime.now()
    }
    
    mongo.db.tasks.insert_one(task)
    
    return jsonify({'status': 'success', 'message': 'Task assigned successfully'})

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
