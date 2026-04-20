import os
import time
import json
from datetime import datetime
from flask import Flask, jsonify, render_template_string
import redis
import psycopg2
from psycopg2 import pool

app = Flask(__name__)

# Configuration from environment
APP_NAME = os.getenv('APP_NAME', 'MyApp')
DATABASE_URL = os.getenv('DATABASE_URL')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')

# Redis connection
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# PostgreSQL connection pool
db_pool = None

def get_db_connection():
    """Get connection from pool or create new pool"""
    global db_pool
    if db_pool is None:
        db_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            host='postgres',
            port=5432,
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )
    return db_pool.getconn()

def release_db_connection(conn):
    """Return connection to pool"""
    if db_pool:
        db_pool.putconn(conn)

# HTML template for main page
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ app_name }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            background: rgba(255,255,255,0.1);
            padding: 30px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        h1 { margin: 0 0 20px 0; }
        .endpoint {
            background: rgba(255,255,255,0.2);
            padding: 10px 15px;
            margin: 10px 0;
            border-radius: 8px;
            font-family: monospace;
        }
        a { color: #ffd700; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ app_name }}</h1>
        <p>Docker Compose Stack: Nginx → Flask → PostgreSQL + Redis</p>
        
        <h3>📡 Available Endpoints:</h3>
        <div class="endpoint">GET <a href="/">/</a> — This page</div>
        <div class="endpoint">GET <a href="/visits">/visits</a> — Visit counter with Redis cache</div>
        <div class="endpoint">GET <a href="/health">/health</a> — Health check JSON</div>
        
        <p style="margin-top: 30px; font-size: 0.9em; opacity: 0.8;">
            Server time: {{ timestamp }}
        </p>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """Main page with app name from environment variable"""
    return render_template_string(
        HTML_TEMPLATE, 
        app_name=APP_NAME,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

@app.route('/visits')
def visits():
    """
    Visit counter with Redis caching (10 second TTL).
    Returns: {"total": N, "cached": true/false}
    """
    cache_key = 'visits:counter'
    cache_ttl = 10  # seconds
    
    # Check cache first
    cached_value = redis_client.get(cache_key)
    
    if cached_value:
        # Return cached value
        return jsonify({
            "total": int(cached_value),
            "cached": True
        })
    
    # Cache miss - increment counter in PostgreSQL
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS visit_log (
                id SERIAL PRIMARY KEY,
                visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert new visit
        cursor.execute("INSERT INTO visit_log (visited_at) VALUES (NOW())")
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM visit_log")
        total = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        
        # Cache the result
        redis_client.setex(cache_key, cache_ttl, total)
        
        return jsonify({
            "total": total,
            "cached": False
        })
        
    except Exception as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({"error": "Database unavailable"}), 503
    finally:
        if conn:
            release_db_connection(conn)

@app.route('/health')
def health():
    """
    Health check endpoint.
    Returns: {"status": "ok", "db": "connected", "redis": "connected"}
    """
    result = {
        "status": "ok",
        "db": "disconnected",
        "redis": "disconnected"
    }
    
    # Check Redis
    try:
        if redis_client.ping():
            result["redis"] = "connected"
    except Exception as e:
        app.logger.error(f"Redis health check failed: {e}")
    
    # Check PostgreSQL
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        result["db"] = "connected"
    except Exception as e:
        app.logger.error(f"PostgreSQL health check failed: {e}")
    finally:
        if conn:
            release_db_connection(conn)
    
    # Set overall status
    if result["db"] == "connected" and result["redis"] == "connected":
        result["status"] = "ok"
    else:
        result["status"] = "degraded"
    
    status_code = 200 if result["status"] == "ok" else 503
    return jsonify(result), status_code

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
