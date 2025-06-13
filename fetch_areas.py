import requests
import time
from collections import defaultdict
import mysql.connector

HEADERS = {"User-Agent": "area-fetcher"}
OVERPASS_URL = "http://overpass-api.de/api/interpreter"

def get_city_coordinates(city):
    url = "https://nominatim.openstreetmap.org/search"
    try:
        response = requests.get(url, params={"q": city, "format": "json", "limit": 1}, headers=HEADERS, timeout=30)
        data = response.json()
        if not data:
            return None, None
        return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print(f"Error fetching city coordinates: {e}")
        return None, None

def get_main_areas(lat, lon, radius=3000):
    query = f"""
    [out:json][timeout:25];
    (
      node["place"~"suburb|locality|quarter"](around:{radius},{lat},{lon});
      way["place"~"suburb|locality|quarter"](around:{radius},{lat},{lon});
      relation["place"~"suburb|locality|quarter"](around:{radius},{lat},{lon});
    );
    out center;
    """
    try:
        response = requests.get(OVERPASS_URL, params={"data": query}, headers=HEADERS, timeout=30)
        data = response.json().get("elements", [])
        result = []
        for elem in data:
            name = elem.get("tags", {}).get("name")
            lat = elem.get("lat", elem.get("center", {}).get("lat"))
            lon = elem.get("lon", elem.get("center", {}).get("lon"))
            if name and lat and lon:
                result.append({"name": name, "lat": lat, "lon": lon})
        return result
    except Exception as e:
        print(f"Error fetching main areas: {e}")
        return []

def get_named_centers_by_area_name(area_name):
    query = f"""
    [out:json][timeout:25];
    relation["name"="{area_name}"];
    map_to_area -> .a;
    (
      node(area.a)["name"];
      way(area.a)["name"];
      relation(area.a)["name"];
    );
    out center;
    """
    try:
        response = requests.get(OVERPASS_URL, params={"data": query}, headers=HEADERS, timeout=30)
        data = response.json().get("elements", [])
        results = []
        for element in data:
            tags = element.get("tags", {})
            name = tags.get("name")
            lat = element.get("lat") or element.get("center", {}).get("lat")
            lon = element.get("lon") or element.get("center", {}).get("lon")
            if name and lat and lon:
                results.append((name, float(lat), float(lon)))
        return results
    except Exception as e:
        print(f"Error in boundary fetch for {area_name}: {e}")
        return []

def get_named_centers_fallback(area_name, lat, lon, radius=1000):
    print(f" Boundary not found for '{area_name}'. Falling back to radius-based search.")
    query = f"""
    [out:json][timeout:30];
    (
      node(around:{radius},{lat},{lon})["name"];
      way(around:{radius},{lat},{lon})["name"];
      relation(around:{radius},{lat},{lon})["name"];
    );
    out center;
    """
    try:
        response = requests.get(OVERPASS_URL, params={"data": query}, headers=HEADERS, timeout=60)
        data = response.json().get("elements", [])
        results = []
        for element in data:
            tags = element.get("tags", {})
            name = tags.get("name")
            elat = element.get("lat") or element.get("center", {}).get("lat")
            elon = element.get("lon") or element.get("center", {}).get("lon")
            if name and elat and elon:
                results.append((name, float(elat), float(elon)))
        return results
    except Exception as e:
        print(f"Fallback error for {area_name}: {e}")
        return []

def insert_data_to_mysql(city_name, area_centers):
    conn = mysql.connector.connect(user="root", password="admin", host="localhost", database="city_data")
    cursor = conn.cursor()
    cursor.execute("INSERT IGNORE INTO cities (name) VALUES (%s)", (city_name,))
    conn.commit()

    cursor.execute("SELECT id FROM cities WHERE name = %s", (city_name,))
    city_id = cursor.fetchone()[0]

    for area, centers in area_centers.items():
        for center_name, lat, lon in centers:
            cursor.execute("""
    INSERT INTO areas (city_id, area_name, center_name, lat, lon, location)
    VALUES (%s, %s, %s, %s, %s, ST_GeomFromText(%s))
""", (city_id, area, center_name, lat, lon, f"POINT({lon} {lat})"))

    conn.commit()
    cursor.close()
    conn.close()
    print('Data Submitted Successfully')

def run_fetcher(city, search_radius=3000, fallback_radius=1000):
    lat, lon = get_city_coordinates(city)
    print(f'{lat=}, {lon=}')
    if not lat or not lon:
        print("Could not get city coordinates.")
        return

    main_areas = get_main_areas(lat, lon, search_radius)
    print(f'{main_areas=}')
    area_centers = defaultdict(list)

    for area in main_areas:
        print(f"Fetching: {area['name']}")
        centers = get_named_centers_by_area_name(area["name"])
        if not centers:
            centers = get_named_centers_fallback(area["name"], area["lat"], area["lon"], fallback_radius)
        area_centers[area["name"]] = centers
        time.sleep(1)

    if area_centers:
        insert_data_to_mysql(city, area_centers)
    else:
        print("No valid center data found to insert.")

if __name__ == "__main__":
    run_fetcher("Ongole, Andhra Pradesh, India", search_radius=10000, fallback_radius=1000)
