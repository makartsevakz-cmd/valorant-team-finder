"""
API Endpoint for Vercel Serverless Functions
"""
import os
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from supabase import create_client

# Supabase credentials
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    supabase = None


class handler(BaseHTTPRequestHandler):
    
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_OPTIONS(self):
        self._set_headers()
    
    def do_GET(self):
        if not supabase:
            self._set_headers(500)
            response = {'success': False, 'error': 'Database not configured'}
            self.wfile.write(json.dumps(response).encode())
            return
        
        path = self.path.split('?')[0]
        
        try:
            if path == '/api/players/today' or path == '/api/players/today/':
                # Получить игроков, играющих сегодня
                today = datetime.now().date().isoformat()
                
                # Query с join
                result = supabase.table('daily_status')\
                    .select('telegram_id, players(*)')\
                    .eq('date', today)\
                    .eq('is_playing', True)\
                    .execute()
                
                players = []
                for item in result.data:
                    if item.get('players'):
                        players.append(item['players'])
                
                response = {
                    'success': True,
                    'date': today,
                    'count': len(players),
                    'players': players
                }
                
            elif path == '/api/stats' or path == '/api/stats/':
                # Получить статистику
                today = datetime.now().date().isoformat()
                
                # Всего игроков
                total_result = supabase.table('players').select('telegram_id', count='exact').execute()
                total_players = total_result.count if hasattr(total_result, 'count') else len(total_result.data)
                
                # Играют сегодня
                playing_result = supabase.table('daily_status')\
                    .select('telegram_id', count='exact')\
                    .eq('date', today)\
                    .eq('is_playing', True)\
                    .execute()
                playing_today = playing_result.count if hasattr(playing_result, 'count') else len(playing_result.data)
                
                response = {
                    'success': True,
                    'total_players': total_players,
                    'playing_today': playing_today
                }
                
            elif path == '/api/health' or path == '/api/health/':
                # Health check
                response = {
                    'success': True,
                    'status': 'healthy',
                    'timestamp': datetime.now().isoformat()
                }
                
            else:
                self._set_headers(404)
                response = {
                    'success': False,
                    'error': 'Endpoint not found'
                }
            
            self._set_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            self._set_headers(500)
            response = {
                'success': False,
                'error': str(e)
            }
            self.wfile.write(json.dumps(response).encode())
