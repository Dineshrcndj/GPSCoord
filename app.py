from flask import Flask, request, jsonify, render_template
from geopy.distance import geodesic
import mysql.connector

app = Flask(__name__)
global submit_radius, fetch_radius
submit_radius=150
fetch_radius=5000
def get_db_connection():
    return mysql.connector.connect(user="root", password="admin", host="localhost", database="city_data")

def fetch_nearby_centers_submissions(lat, lon, radius_meters):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """

        SELECT area_name, center_name, lat, lon, submitted_at
        FROM submissions
        WHERE ST_Distance_Sphere(POINT(lon, lat), POINT(%s, %s)) <= %s
    """
    cursor.execute(query, (lon, lat, radius_meters))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def fetch_nearby_centers(lat, lon, radius_meters):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT area_name, center_name, lat, lon
        FROM areas
        WHERE ST_Distance_Sphere(POINT(lon, lat), POINT(%s, %s)) <= %s
    """
    cursor.execute(query, (lon, lat, radius_meters))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results


def insert_submission(area_name, center_name, lat, lon):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO submissions (area_name, center_name, lat, lon, location)
    VALUES (%s, %s, %s, %s, ST_GeomFromText(%s))
""", (
    area_name,
    center_name,
    lat,
    lon,
    f"POINT({lon} {lat})"
))

    conn.commit()
    cursor.close()
    conn.close()

def fetch_submissions():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM submissions ORDER BY submitted_at DESC")
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

@app.route("/")
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Delete submissions older than 2 hours
    cursor.execute("""
        DELETE FROM submissions 
        WHERE submitted_at < NOW() - INTERVAL 2 HOUR
    """)
    conn.commit()
    
    # Fetch remaining submissions
    cursor.execute("""
        SELECT * FROM submissions 
        ORDER BY submitted_at DESC
    """)
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template("dashboard.html")

@app.route("/static/styles.css")
def serve_css():
    return """
    body {
        font-family: Arial, sans-serif;
        margin: 20px;
        padding: 20px;
    }
    .container {
        max-width: 1200px;
        margin: 0 auto;
    }
    .btn-primary {
        margin: 10px 0;
    }
    .table {
        margin-top: 20px;
    }
    .form-group {
        margin-bottom: 15px;
    }
    """, 200, {'Content-Type': 'text/css'}

@app.route("/get_nearby_centers", methods=["POST"])
def get_nearby_centers():
    data = request.json
    lat, lon = data['lat'], data['lon']
    print(f'{lat=},{lon=}')
    centers = fetch_nearby_centers_submissions(lat, lon, fetch_radius)
    for center in centers:
        center['distance'] = round(geodesic((lat, lon), (center['lat'], center['lon'])).meters, 2)
    return jsonify(centers)

@app.route("/get_addable_locations", methods=["POST"])
def get_addable_locations():
    data = request.json
    lat, lon = data['lat'], data['lon']
    centers = fetch_nearby_centers(lat, lon, submit_radius)
    for center in centers:
        center['distance'] = round(geodesic((lat, lon), (center['lat'], center['lon'])).meters, 2)
    return jsonify(centers)

@app.route("/add_location", methods=["POST"])
def add_location():
    data = request.json
    insert_submission(data['area_name'], data['center_name'], data['lat'], data['lon'])
    return jsonify({"status": "success"})

@app.route("/get_submissions")
def get_submissions():
    return jsonify(fetch_submissions())

if __name__ == "__main__":
    app.run(debug=True)