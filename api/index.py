from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Supabase credentials
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

# Initialize Supabase
supabase_client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase init error: {e}")


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'supabase_connected': bool(supabase_client),
        'has_url': bool(SUPABASE_URL),
        'has_key': bool(SUPABASE_KEY)
    })


@app.route('/api/stats')
def stats():
    """Get statistics"""
    if not supabase_client:
        return jsonify({
            'success': False,
            'error': 'Database not configured'
        }), 500
    
    try:
        today = datetime.now().date().isoformat()
        
        # Total players
        total_response = supabase_client.table('players').select('telegram_id').execute()
        total_players = len(total_response.data) if total_response.data else 0
        
        # Playing today
        playing_response = supabase_client.table('daily_status')\
            .select('telegram_id')\
            .eq('date', today)\
            .eq('is_playing', True)\
            .execute()
        playing_today = len(playing_response.data) if playing_response.data else 0
        
        return jsonify({
            'success': True,
            'total_players': total_players,
            'playing_today': playing_today,
            'date': today
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/players/today')
def players_today():
    """Get players playing today"""
    if not supabase_client:
        return jsonify({
            'success': False,
            'error': 'Database not configured'
        }), 500
    
    try:
        today = datetime.now().date().isoformat()
        
        # Query with join
        response = supabase_client.table('daily_status')\
            .select('telegram_id, players(*)')\
            .eq('date', today)\
            .eq('is_playing', True)\
            .execute()
        
        players = []
        if response.data:
            for item in response.data:
                if item.get('players'):
                    players.append(item['players'])
        
        return jsonify({
            'success': True,
            'date': today,
            'count': len(players),
            'players': players
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# For Vercel
def handler(request, response):
    with app.request_context(request.environ):
        return app.full_dispatch_request()