from app import app
from models import db, User

def init_database():
    """Инициализация базы данных с тестовыми данными"""
    with app.app_context():
        # Создаём все таблицы
        db.create_all()
        
        # Проверяем, есть ли уже пользователи
        if User.query.count() == 0:
            # Создаём тестового пользователя
            test_user = User(username='test')
            test_user.set_password('test123')
            test_user.balance = 5000.0
            
            db.session.add(test_user)
            db.session.commit()
            
            print("База данных инициализирована!")
            print("Тестовый пользователь создан:")
            print("Логин: test")
            print("Пароль: test123")
            print("Баланс: 5000₽")
        else:
            print("База данных уже содержит данные")

if __name__ == '__main__':
    init_database()
