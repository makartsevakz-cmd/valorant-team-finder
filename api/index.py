"""
API Endpoint for Vercel Serverless Functions
"""
import os
import json
from datetime import datetime
from supabase import create_client

# Supabase credentials
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Failed to connect to Supabase: {e}")


def handler(request):
    """Main handler for Vercel serverless function"""
    
    # CORS headers
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type': 'application/json'
    }
    
    # Handle OPTIONS request
    if request.method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }
    
    # Check Supabase connection
    if not supabase:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'success': False,
                'error': 'Database not configured. Please check SUPABASE_URL and SUPABASE_KEY environment variables.'
            })
        }
    
    # Get path from request
    path = request.url.path if hasattr(request.url, 'path') else request.path
    
    try:
        if '/api/players/today' in path:
            # Get players playing today
            today = datetime.now().date().isoformat()
            
            result = supabase.table('daily_status')\
                .select('telegram_id, players(*)')\
                .eq('date', today)\
                .eq('is_playing', True)\
                .execute()
            
            players = []
            if result.data:
                for item in result.data:
                    if item.get('players'):
                        players.append(item['players'])
            
            response_data = {
                'success': True,
                'date': today,
                'count': len(players),
                'players': players
            }
            
        elif '/api/stats' in path:
            # Get statistics
            today = datetime.now().date().isoformat()
            
            # Total players
            total_result = supabase.table('players').select('telegram_id', count='exact').execute()
            total_players = len(total_result.data) if total_result.data else 0
            
            # Playing today
            playing_result = supabase.table('daily_status')\
                .select('telegram_id', count='exact')\
                .eq('date', today)\
                .eq('is_playing', True)\
                .execute()
            playing_today = len(playing_result.data) if playing_result.data else 0
            
            response_data = {
                'success': True,
                'total_players': total_players,
                'playing_today': playing_today
            }
            
        elif '/api/health' in path:
            # Health check
            response_data = {
                'success': True,
                'status': 'healthy',
                'timestamp': datetime.now().isoformat()
            }
            
        else:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'success': False,
                    'error': 'Endpoint not found'
                })
            }
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_data)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }