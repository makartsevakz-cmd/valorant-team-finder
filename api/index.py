"""
Vercel Serverless Function - Native Handler Format
"""
from http.server import BaseHTTPRequestHandler
import os
import json
from datetime import datetime
from urllib.parse import urlparse

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
        print(f"Supabase initialization error: {e}")


class handler(BaseHTTPRequestHandler):
    """Vercel handler class"""
    
    def _set_headers(self, status=200):
        """Set response headers"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _send_json(self, data, status=200):
        """Send JSON response"""
        self._set_headers(status)
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self._set_headers(200)
    
    def do_GET(self):
        """Handle GET requests"""
        
        # Parse path
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Check Supabase connection
        if not supabase_client:
            return self._send_json({
                'success': False,
                'error': 'Database not configured',
                'has_url': bool(SUPABASE_URL),
                'has_key': bool(SUPABASE_KEY)
            }, 500)
        
        try:
            # Route to appropriate handler
            if 'health' in path:
                self._handle_health()
            elif 'stats' in path:
                self._handle_stats()
            elif 'players/today' in path or path.endswith('/today'):
                self._handle_players_today()
            else:
                self._send_json({
                    'success': False,
                    'error': 'Endpoint not found',
                    'path': path
                }, 404)
        except Exception as e:
            self._send_json({
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }, 500)
    
    def _handle_health(self):
        """Health check endpoint"""
        self._send_json({
            'success': True,
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'supabase_connected': bool(supabase_client),
            'url_preview': SUPABASE_URL[:30] + '...' if len(SUPABASE_URL) > 30 else SUPABASE_URL
        })
    
    def _handle_stats(self):
        """Get statistics"""
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
            
            self._send_json({
                'success': True,
                'total_players': total_players,
                'playing_today': playing_today,
                'date': today
            })
        except Exception as e:
            self._send_json({
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }, 500)
    
    def _handle_players_today(self):
        """Get players playing today"""
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
            
            self._send_json({
                'success': True,
                'date': today,
                'count': len(players),
                'players': players
            })
        except Exception as e:
            self._send_json({
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }, 500)
