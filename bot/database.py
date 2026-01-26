"""
Database module for Supabase integration
"""
import os
from supabase import create_client, Client
from datetime import datetime

# Supabase credentials from environment variables
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def create_player(telegram_id: int, telegram_username: str, telegram_first_name: str,
                  valorant_nick: str, rank: str, roles: list):
    """Создать или обновить профиль игрока"""
    try:
        data = {
            'telegram_id': telegram_id,
            'telegram_username': telegram_username,
            'telegram_first_name': telegram_first_name,
            'valorant_nick': valorant_nick,
            'rank': rank,
            'roles': roles,
            'updated_at': datetime.now().isoformat()
        }
        
        result = supabase.table('players').upsert(data).execute()
        return True
    except Exception as e:
        print(f"Error creating player: {e}")
        return False


def get_player(telegram_id: int):
    """Получить профиль игрока"""
    try:
        result = supabase.table('players').select('*').eq('telegram_id', telegram_id).execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        print(f"Error getting player: {e}")
        return None


def update_daily_status(telegram_id: int, is_playing: bool):
    """Обновить статус игрока на сегодня"""
    try:
        today = datetime.now().date().isoformat()
        data = {
            'telegram_id': telegram_id,
            'date': today,
            'is_playing': is_playing,
            'updated_at': datetime.now().isoformat()
        }
        
        result = supabase.table('daily_status').upsert(data).execute()
        return True
    except Exception as e:
        print(f"Error updating daily status: {e}")
        return False


def get_daily_status(telegram_id: int):
    """Получить статус игрока на сегодня"""
    try:
        today = datetime.now().date().isoformat()
        result = supabase.table('daily_status').select('*').eq('telegram_id', telegram_id).eq('date', today).execute()
        if result.data:
            return result.data[0]['is_playing']
        return False
    except Exception as e:
        print(f"Error getting daily status: {e}")
        return False


def get_all_players():
    """Получить всех зарегистрированных игроков"""
    try:
        result = supabase.table('players').select('*').execute()
        return result.data
    except Exception as e:
        print(f"Error getting all players: {e}")
        return []


def get_players_playing_today():
    """Получить игроков, играющих сегодня"""
    try:
        today = datetime.now().date().isoformat()
        
        # Получаем игроков с активным статусом на сегодня
        result = supabase.table('daily_status')\
            .select('telegram_id, players(*)')\
            .eq('date', today)\
            .eq('is_playing', True)\
            .execute()
        
        players = []
        for item in result.data:
            if item.get('players'):
                players.append(item['players'])
        
        return players
    except Exception as e:
        print(f"Error getting players playing today: {e}")
        return []
