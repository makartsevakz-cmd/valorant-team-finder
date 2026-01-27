"""
Database module for Supabase integration (v2)
С поддержкой временных слотов
"""
import os
from supabase import create_client, Client
from datetime import datetime

# Supabase credentials from environment variables
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def save_player(telegram_id: int, valorant_nick: str, rank: str, roles: list):
    """Создать или обновить профиль игрока"""
    try:
        data = {
            'telegram_id': telegram_id,
            'valorant_nick': valorant_nick,
            'rank': rank,
            'roles': roles,
        }
        
        result = supabase.table('players').upsert(data).execute()
        return True
    except Exception as e:
        print(f"Error saving player: {e}")
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


def update_daily_status(telegram_id: int, date: str, is_playing: bool, time_slots: list = None):
    """Обновить статус игрока на конкретную дату с временными слотами"""
    try:
        if time_slots is None:
            time_slots = []
        
        data = {
            'telegram_id': telegram_id,
            'date': date,
            'is_playing': is_playing,
            'time_slots': time_slots,
            'updated_at': datetime.now().isoformat()
        }
        
        result = supabase.table('daily_status').upsert(data).execute()
        return True
    except Exception as e:
        print(f"Error updating daily status: {e}")
        return False


def get_daily_status(telegram_id: int, date: str):
    """Получить статус игрока на конкретную дату"""
    try:
        result = supabase.table('daily_status')\
            .select('*')\
            .eq('telegram_id', telegram_id)\
            .eq('date', date)\
            .execute()
        
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        print(f"Error getting daily status: {e}")
        return None


def get_all_players():
    """Получить всех зарегистрированных игроков"""
    try:
        result = supabase.table('players').select('*').execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting all players: {e}")
        return []


def get_players_playing_today():
    """Получить игроков, играющих сегодня"""
    try:
        today = datetime.now().date().isoformat()
        
        # Получаем игроков с активным статусом на сегодня
        result = supabase.table('daily_status')\
            .select('telegram_id, time_slots, players(*)')\
            .eq('date', today)\
            .eq('is_playing', True)\
            .execute()
        
        players = []
        for item in result.data:
            if item.get('players'):
                player_data = item['players'].copy()
                player_data['time_slots'] = item.get('time_slots', [])
                players.append(player_data)
        
        return players
    except Exception as e:
        print(f"Error getting players playing today: {e}")
        return []


def get_players_by_slots(date: str, time_slots: list, limit: int = 10, exclude_id: int = None):
    """
    Получить игроков, играющих в указанные временные слоты
    
    Args:
        date: Дата в формате YYYY-MM-DD
        time_slots: Список временных слотов ['morning', 'evening', ...]
        limit: Максимальное количество игроков
        exclude_id: ID игрока которого нужно исключить из результатов
    """
    try:
        # Получаем всех играющих в эту дату
        query = supabase.table('daily_status')\
            .select('telegram_id, time_slots, players(*)')\
            .eq('date', date)\
            .eq('is_playing', True)
        
        if exclude_id:
            query = query.neq('telegram_id', exclude_id)
        
        result = query.limit(limit).execute()
        
        matching_players = []
        for item in result.data:
            item_slots = item.get('time_slots', [])
            # Проверяем есть ли пересечение слотов
            if any(slot in item_slots for slot in time_slots):
                if item.get('players'):
                    player_data = item['players'].copy()
                    player_data['time_slots'] = item_slots
                    matching_players.append(player_data)
        
        return matching_players[:limit]
    except Exception as e:
        print(f"Error getting players by slots: {e}")
        return []


def get_players_by_timeslot(date: str, timeslot: str):
    """
    Получить игроков, играющих в конкретный временной слот
    
    Args:
        date: Дата в формате YYYY-MM-DD
        timeslot: Временной слот ('morning', 'day', 'evening', 'night')
    """
    try:
        # Используем contains для проверки наличия элемента в массиве
        result = supabase.table('daily_status')\
            .select('telegram_id, time_slots, players(*)')\
            .eq('date', date)\
            .eq('is_playing', True)\
            .contains('time_slots', [timeslot])\
            .execute()
        
        players = []
        for item in result.data:
            if item.get('players'):
                player_data = item['players'].copy()
                player_data['time_slots'] = item.get('time_slots', [])
                players.append(player_data)
        
        return players
    except Exception as e:
        print(f"Error getting players by timeslot: {e}")
        return []


def delete_player(telegram_id: int):
    """Удалить игрока (каскадно удалятся и его daily_status)"""
    try:
        result = supabase.table('players').delete().eq('telegram_id', telegram_id).execute()
        return True
    except Exception as e:
        print(f"Error deleting player: {e}")
        return False
