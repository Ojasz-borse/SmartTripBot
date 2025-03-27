from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify, send_file
import sqlite3
from datetime import datetime, timedelta
import cohere
import os
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import hashlib
from pydrive2.auth import GoogleAuth
from io import BytesIO
import tempfile
from pydrive2.drive import GoogleDrive
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from flask_caching import Cache
from flask_migrate import Migrate
from sqlalchemy import Column, Integer, String, Date
from datetime import datetime
from translatepy import Translator
from models import db, Document

# Initialize Flask app
app = Flask(__name__)

# Configure the app
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['SECRET_KEY'] = '64e7fb6bb973267fc9f922883eaa83d758c1607c95d2e8a14ae2b2d41fa71065'

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)

# Initialize other components
metadata = MetaData()
translator = Translator()
co = cohere.Client('Y4hXn0B2VIGGW3i52mRoO7EN1em88kKNwnz2lBwd')

# Create upload folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Define models
class ChecklistItem(db.Model):
    __tablename__ = 'checklist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    item = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ChecklistItem {self.item}>'

class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    cover_image = db.Column(db.String(200), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    image_filenames = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<Trip {self.name}>'

class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(150), nullable=False)

# Create database tables
with app.app_context():
    db.create_all()

# Helper functions
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL,
            travel_type TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            file_url TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_text TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            source_lang TEXT NOT NULL,
            target_lang TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Routes
@app.route('/dashboard1')
def dashboard1():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        documents = Document.query.filter_by(user_id=session['user_id']).all()
        return render_template('dashboard1.html', documents=documents)
    except Exception as e:
        print(f"Error in dashboard1: {str(e)}")
        flash('Error loading documents', 'error')
        return render_template('dashboard1.html', documents=[])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action = request.form.get('action')
        conn = get_db_connection()
        cursor = conn.cursor()

        if action == 'register':
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            try:
                cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
                conn.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('Email already exists. Please use a different one.', 'danger')

        elif action == 'login':
            email = request.form['email']
            password = request.form['password']
            cursor.execute('SELECT id, username FROM users WHERE email = ? AND password = ?', (email, password))
            user = cursor.fetchone()
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password. Please try again.', 'danger')

        conn.close()
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session.get('username'))

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/currencycon')
def currencycon():
    return render_template('currencycon.html')

@app.route('/check')
def check():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        items = ChecklistItem.query.filter_by(user_id=session['user_id']).order_by(ChecklistItem.created_at.desc()).all()
        return render_template('checklist.html', items=items)
    except Exception as e:
        print(f"Error fetching checklist items: {str(e)}")
        flash('Error loading checklist items', 'error')
        return render_template('checklist.html', items=[])

@app.route('/emer')
def emer():
    checklist = ChecklistItem.query.all()
    return render_template('emergency.html', checklist=checklist)

@app.route('/add_images', methods=['POST'])
def add_images():
    if 'file' not in request.files:
        return redirect(request.url)
    
    files = request.files.getlist('file')  # Get multiple files
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Store the file info in the database
            new_image = Image(filename=filename)
            db.session.add(new_image)
            db.session.commit()

    return redirect(url_for('index'))
    
# Route to add a trip
@app.route('/add_trip', methods=['GET', 'POST'])
def add_trip():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            
            if not all([name, description, start_date, end_date]):
                return jsonify({
                    'success': False,
                    'message': 'All fields are required'
                }), 400
            
            # Convert string dates to datetime objects
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                if end_date < start_date:
                    return jsonify({
                        'success': False,
                        'message': 'End date cannot be before start date'
                    }), 400
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'Invalid date format'
                }), 400

            # Handle cover image upload
            cover_image = request.files.get('cover_image')
            cover_image_filename = None
            if cover_image and cover_image.filename:
                if not allowed_file(cover_image.filename):
                    return jsonify({
                        'success': False,
                        'message': 'Invalid file type for cover image'
                    }), 400
                cover_image_filename = secure_filename(cover_image.filename)
                cover_image_path = os.path.join(app.config['UPLOAD_FOLDER'], cover_image_filename)
                cover_image.save(cover_image_path)
            
            # Handle multiple images upload
            image_files = request.files.getlist('images')
            image_filenames = []
            upload_folder = app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            for image in image_files:
                if image.filename:
                    if not allowed_file(image.filename):
                        continue  # Skip invalid files
                    filename = secure_filename(image.filename)
                    image_path = os.path.join(upload_folder, filename)
                    image.save(image_path)
                    image_filenames.append(filename)

            # Create new trip
            new_trip = Trip(
                name=name,
                description=description,
                cover_image=cover_image_filename,
                start_date=start_date,
                end_date=end_date,
                image_filenames=",".join(image_filenames) if image_filenames else ""
            )
            
            db.session.add(new_trip)
            db.session.commit()

            return jsonify({
                'success': True,
                'trip': {
                    'id': new_trip.id,
                    'name': new_trip.name,
                    'description': new_trip.description,
                    'cover_image': new_trip.cover_image,
                    'start_date': new_trip.start_date.isoformat(),
                    'end_date': new_trip.end_date.isoformat(),
                    'image_filenames': new_trip.image_filenames
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500

    return render_template('add_trip.html')

@app.route('/delete_image/<filename>/<int:trip_id>', methods=['DELETE'])
def delete_image(filename, trip_id):
    # Fetch the trip associated with the image
    trip = Trip.query.get(trip_id)
    if trip:
        try:
            # Remove the image from the server
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(image_path):
                os.remove(image_path)

            # Remove the image from the trip's list of image filenames
            image_files = trip.image_filenames.split(',')
            image_files = [img for img in image_files if img != filename]
            trip.image_filenames = ','.join(image_files)
            
            # Commit changes to the database
            db.session.commit()

            return jsonify({'message': 'Image deleted successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': 'Error deleting image', 'error': str(e)}), 500
    else:
        return jsonify({'message': 'Trip not found'}), 404

# Route: Add Item
@app.route('/add_item', methods=['POST'])
def add_item():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        item_text = request.form.get('item')
        if item_text:
            new_item = ChecklistItem(
                user_id=session['user_id'],
                item=item_text,
                completed=False
            )
            db.session.add(new_item)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'item': {
                    'id': new_item.id,
                    'text': new_item.item,
                    'completed': new_item.completed
                }
            })
        return jsonify({'error': 'No item text provided'}), 400
    except Exception as e:
        db.session.rollback()
        print(f"Error adding checklist item: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Route: Delete Item
@app.route('/delete/<int:item_id>')
def delete_item(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        item = ChecklistItem.query.filter_by(id=item_id, user_id=session['user_id']).first_or_404()
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting checklist item: {str(e)}")
        flash(f'Error deleting item: {str(e)}', 'error')
    
    return redirect(url_for('check'))

# Route: Toggle Item
@app.route('/toggle/<int:item_id>')
def toggle_item(item_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        item = ChecklistItem.query.filter_by(id=item_id, user_id=session['user_id']).first_or_404()
        item.completed = not item.completed
        db.session.commit()
        return jsonify({
            'success': True,
            'completed': item.completed
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error toggling checklist item: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Document deletion route with a different path
@app.route('/delete_document/<int:doc_id>')
def delete_document(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        document = Document.query.filter_by(id=doc_id, user_id=session['user_id']).first_or_404()
        
        # Delete the file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete the database record
        db.session.delete(document)
        db.session.commit()
        
        flash('Document deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting document: {str(e)}', 'error')
    
    return redirect(url_for('dashboard1'))

@app.route('/trips')
def trips():
    # Fetch all trips from the database
    all_trips = Trip.query.all()
    # Pass the trips list to the template
    return render_template('trips.html', trips=all_trips)

# Route to display trip details
@app.route('/trips/<int:trip_id>')
def trip_detail(trip_id):
    # Fetch the specific trip from the database
    trip = Trip.query.get_or_404(trip_id)
    return render_template('trip_detail.html', trip=trip)

# Route to save (edit) trip data
@app.route('/save_trip/<int:trip_id>', methods=['POST'])
def save_trip(trip_id):
    try:
        trip = Trip.query.get_or_404(trip_id)
        
        # Validate required fields
        name = request.form.get('name')
        description = request.form.get('description')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not all([name, description, start_date, end_date]):
            return jsonify({
                'success': False,
                'message': 'All fields are required'
            }), 400
        
        # Validate dates
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if end_date < start_date:
                return jsonify({
                    'success': False,
                    'message': 'End date cannot be before start date'
                }), 400
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid date format'
            }), 400

        # Update trip data
        trip.name = name
        trip.description = description
        trip.start_date = start_date
        trip.end_date = end_date

        # Handle cover image upload
        if 'cover_image' in request.files:
            cover_image = request.files['cover_image']
            if cover_image and cover_image.filename:
                if not allowed_file(cover_image.filename):
                    return jsonify({
                        'success': False,
                        'message': 'Invalid file type for cover image'
                    }), 400
                
                # Delete old cover image
                if trip.cover_image:
                    old_cover_path = os.path.join(app.config['UPLOAD_FOLDER'], trip.cover_image)
                    if os.path.exists(old_cover_path):
                        os.remove(old_cover_path)
                
                # Save new cover image
                cover_image_filename = secure_filename(cover_image.filename)
                cover_image_path = os.path.join(app.config['UPLOAD_FOLDER'], cover_image_filename)
                cover_image.save(cover_image_path)
                trip.cover_image = cover_image_filename

        # Handle additional images
        if 'images' in request.files:
            new_images = request.files.getlist('images')
            if new_images:
                # Delete old images
                if trip.image_filenames:
                    for old_filename in trip.image_filenames.split(','):
                        if old_filename:
                            old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_filename)
                            if os.path.exists(old_path):
                                os.remove(old_path)
                
                # Save new images
                image_filenames = []
                for image in new_images:
                    if image and image.filename:
                        if not allowed_file(image.filename):
                            continue
                        filename = secure_filename(image.filename)
                        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        image.save(image_path)
                        image_filenames.append(filename)
                
                trip.image_filenames = ",".join(image_filenames)

        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Trip updated successfully',
            'trip': {
                'id': trip.id,
                'name': trip.name,
                'description': trip.description,
                'cover_image': trip.cover_image,
                'start_date': trip.start_date.isoformat(),
                'end_date': trip.end_date.isoformat(),
                'image_filenames': trip.image_filenames
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Route to display all trips
@app.route('/trips')
def show_trips():
    # Fetch all trips from the database
    all_trips = Trip.query.all()
    return render_template('trips.html', trips=all_trips)

@app.route('/delete_trip/<int:trip_id>', methods=['DELETE'])
def delete_trip(trip_id):
    try:
        trip = Trip.query.get_or_404(trip_id)
        
        # Delete cover image
        if trip.cover_image:
            cover_image_path = os.path.join(app.config['UPLOAD_FOLDER'], trip.cover_image)
            if os.path.exists(cover_image_path):
                os.remove(cover_image_path)
        
        # Delete additional images
        if trip.image_filenames:
            for filename in trip.image_filenames.split(','):
                if filename:
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    if os.path.exists(image_path):
                        os.remove(image_path)
        
        db.session.delete(trip)
        db.session.commit()
        
        return jsonify({'message': 'Trip deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 500

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/budget', methods=['GET', 'POST'])
def budget():
    if request.method == 'POST':
        budget = float(request.form['budget'])
        days = int(request.form['days'])
        expenses = request.form['expenses']

        # Query the AI for recommendations
        recommendations = query_budget_ai(budget, days, expenses)

        return render_template(
            'budget.html', 
            budget=budget, 
            days=days, 
            expenses=expenses, 
            recommendations=recommendations,
            show_result=True
        )

    return render_template('budget.html', show_result=False)

def query_budget_ai(budget, days, expenses):
    prompt = (
        f"Suggest travel destinations and activities for a budget of {budget} INR over {days} days. "
        f"Consider the following expenses: {expenses}. Recommend destinations that fit the budget, "
        f"including approximate costs for accommodation, food, and transportation. Provide practical activities "
        f"for each day based on the budget."
    )

    try:
        response = co.generate(
            model='command-r-plus',
            prompt=prompt,
            max_tokens=500,
            temperature=0.7
        )

        if not response or not response.generations:
            raise ValueError("Empty response from AI")

        raw_text = response.generations[0].text.strip()

        # Parse AI recommendations into a dictionary with day-wise activities
        recommendations = {}
        lines = raw_text.split('\n')
        current_day = None

        for line in lines:
            line = line.strip()
            if line.lower().startswith('day'):
                current_day = line
                recommendations[current_day] = []
            elif current_day:
                recommendations[current_day].append(line)

        return recommendations

    except Exception as e:
        print(f"Error querying Cohere API: {e}")
        return {"Error": ["The AI could not generate recommendations. Please try again."]}

# AI Analysis route
@app.route('/ai', methods=['GET', 'POST'])
def ai():
    date_range = []  # Define date_range in case of error
    age = None  # Initialize age variable

    if request.method == 'POST':
        destination = request.form['destination']
        days = int(request.form['days'])
        start_date = request.form['start-date']
        age = request.form['age']  # Capture age input

        # Calculate date range
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        date_range = [(start_date_obj + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]

        # Query Cohere API for recommendations
        ai_response = query_ai(destination, days, date_range)
        if not ai_response:
            return render_template('ai.html', error="AI could not generate recommendations. Please try again.", date_range=date_range)

        return render_template('ai.html', destination=destination, days=days, date_range=date_range, ai_response=ai_response, age=age)

    return render_template('ai.html', date_range=date_range, age=age)  # Ensure age is passed here as well

def query_ai(destination, days, date_range):
    """
    Query the Cohere API for a detailed list of clothing, accessories, and food recommendations
    for a given destination and trip duration.
    """
    prompt = (
        f"You are a travel expert. Provide a detailed list of essential items to pack for a trip to {destination} for {days} days, "
        f"starting from {date_range[0]}. Include clothing recommendations based on weather, cultural aspects, and activities. "
        f"Suggest must-have accessories and travel gear. Also, provide a list of the most famous local foods that visitors must try. "
        f"Ensure the response is structured in sections: 'Clothing', 'Accessories', and 'Famous Foods'."
    )

    try:
        response = co.generate(
            model='command-r-plus',  # Use a suitable Cohere model
            prompt=prompt,
            max_tokens=700,  # Increase the response length for more details
            temperature=0.8  # Slightly higher temperature for creative recommendations
        )

        print("Full API Response:", response)

        if not response or not response.generations:
            raise ValueError("Empty response from AI")

        text = response.generations[0].text.strip()
        print("Generated Text:", text)

        # Improved Extraction Logic
        recommendations = {
            'clothing': [],
            'accessories': [],
            'food': [],
        }

        # Use regular expressions to handle different formats
        import re

        clothing_match = re.search(r"Clothing[:\n](.*?)(?:\nAccessories:|\nFamous Foods:|$)", text, re.DOTALL)
        accessories_match = re.search(r"Accessories[:\n](.*?)(?:\nFamous Foods:|$)", text, re.DOTALL)
        food_match = re.search(r"Famous Foods[:\n](.*?)(?:$)", text, re.DOTALL)

        if clothing_match:
            recommendations['clothing'] = [item.strip() for item in clothing_match.group(1).split('\n') if item.strip()]
        if accessories_match:
            recommendations['accessories'] = [item.strip() for item in accessories_match.group(1).split('\n') if item.strip()]
        if food_match:
            recommendations['food'] = [item.strip() for item in food_match.group(1).split('\n') if item.strip()]

        return recommendations

    except Exception as e:
        print(f"Error querying Cohere API: {e}")
        return None

@app.route('/translate')
def translate():
    return render_template('language.html')

# Translation API
@app.route('/translate', methods=['POST'])
def translate_text():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        original_text = data.get('text')
        source_lang = data.get('source_lang', 'auto')
        target_lang = data.get('target_lang')

        if not original_text or not target_lang:
            return jsonify({'error': 'Missing required fields'}), 400

        # Handle 'auto' source language
        if source_lang == 'auto':
            source_lang = None  # translatepy will auto-detect if None

        # Handle Chinese simplified code
        if source_lang == 'zh-cn':
            source_lang = 'zh'
        if target_lang == 'zh-cn':
            target_lang = 'zh'

        # Perform translation
        try:
            translated = translator.translate(
                original_text,
                source_language=source_lang,
                destination_language=target_lang
            )

            # Save translation to database
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO translations (original_text, translated_text, source_lang, target_lang)
                VALUES (?, ?, ?, ?)
            ''', (original_text, translated.result, source_lang or 'auto', target_lang))
            conn.commit()
            conn.close()

            return jsonify({
                'original_text': original_text,
                'translated_text': translated.result,
                'source_lang': source_lang or 'auto',
                'target_lang': target_lang
            })

        except Exception as e:
            print(f"Translation error: {str(e)}")
            return jsonify({'error': 'Translation failed'}), 500

    except Exception as e:
        print(f"Server error: {str(e)}")
        return jsonify({'error': 'Server error'}), 500

# Fetch translation history
@app.route('/history', methods=['GET'])
def get_history():
    conn = get_db_connection()
    translations = conn.execute('SELECT * FROM translations ORDER BY id DESC').fetchall()
    conn.close()
    return jsonify([dict(translation) for translation in translations])

def send_email(to_email, subject, body):
    sender_email = os.getenv("EMAIL_USER", "your_email@gmail.com")
    sender_password = os.getenv("EMAIL_PASS", "your_email_password")

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print("Error sending email:", e)

def check_expiry_and_notify():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT users.email, documents.doc_type, documents.expiry_date FROM documents 
                      JOIN users ON documents.user_id = users.id''')
    documents = cursor.fetchall()
    conn.close()

    today = datetime.today().date()
    for email, doc_type, expiry_date in documents:
        expiry_date_obj = datetime.strptime(expiry_date, '%Y-%m-%d').date()
        if (expiry_date_obj - today).days <= 7:
            send_email(email, "Document Expiry Notice", f"Your {doc_type} is expiring on {expiry_date}.")

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            doc_type = request.form.get('doc_type')
            travel_type = request.form.get('travel_type')
            expiry_date = request.form.get('expiry_date')
            file = request.files.get('file')

            if not all([doc_type, travel_type, expiry_date, file]):
                flash('All fields are required', 'error')
                return redirect(url_for('upload'))

            if not allowed_file(file.filename):
                flash('Invalid file type', 'error')
                return redirect(url_for('upload'))

            # Save file locally
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Create document record
            new_document = Document(
                user_id=session['user_id'],
                doc_type=doc_type,
                travel_type=travel_type,
                expiry_date=datetime.strptime(expiry_date, '%Y-%m-%d').date(),
                filename=filename
            )
            
            db.session.add(new_document)
            db.session.commit()

            flash('Document uploaded successfully!', 'success')
            return redirect(url_for('dashboard1'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error uploading document: {str(e)}', 'error')
            return redirect(url_for('upload'))

    return render_template('upload.html')

@app.route('/download/<int:doc_id>')
def download_document(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        document = Document.query.filter_by(id=doc_id, user_id=session['user_id']).first_or_404()
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.filename)
        
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            flash('File not found', 'error')
    except Exception as e:
        flash(f'Error downloading document: {str(e)}', 'error')
    
    return redirect(url_for('dashboard1'))

if __name__ == '__main__':
    app.run(debug=True, port=5003)  # Change 5001 to any desired port
