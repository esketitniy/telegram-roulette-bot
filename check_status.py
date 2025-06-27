#!/usr/bin/env python3
"""
Скрипт для проверки состояния приложения рулетки
"""

import requests
import json
import time
from datetime import datetime

def check_app_status(base_url="http://localhost:5000"):
    """Проверяет состояние приложения"""
    
    print("🔍 Проверка состояния приложения рулетки")
    print("=" * 50)
    
    # Проверка основной страницы
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"✅ Главная страница: {response.status_code}")
    except Exception as e:
        print(f"❌ Главная страница недоступна: {e}")
        return False
    
    # Проверка API состояния игры
    try:
        response = requests.get(f"{base_url}/api/game_state", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API состояния игры: {response.status_code}")
            print(f"   Статус: {data.get('status', 'unknown')}")
            print(f"   Раунд: {data.get('round_number', 'unknown')}")
            print(f"   Время: {data.get('time_left', 'unknown')}с")
        else:
            print(f"⚠️ API состояния игры: {response.status_code}")
    except Exception as e:
        print(f"❌ API состояния игры недоступно: {e}")
    
    # Проверка API результатов
    try:
        response = requests.get(f"{base_url}/api/recent_results", timeout=5)
        if response.status_code == 200:
            data = response.json()
            results_count = len(data.get('results', []))
            print(f"✅ API результатов: {response.status_code} ({results_count} результатов)")
        else:
            print(f"⚠️ API результатов: {response.status_code}")
    except Exception as e:
        print(f"❌ API результатов недоступно: {e}")
    
    # Проверка Socket.IO
    try:
        import socketio
        sio = socketio.SimpleClient()
        
        @sio.event
        def connect():
            print("✅ Socket.IO подключение установлено")
        
        @sio.event
        def game_state(data):
            print(f"✅ Получено состояние игры через Socket.IO: {data}")
        
        sio.connect(base_url, wait_timeout=5)
        time.sleep(2)
        sio.disconnect()
        
    except Exception as e:
        print(f"❌ Socket.IO недоступен: {e}")
    
    print("=" * 50)
    print(f"⏰ Проверка завершена: {datetime.now().strftime('%H:%M:%S')}")
    return True

if __name__ == "__main__":
    import sys
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    check_app_status(base_url)
