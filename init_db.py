from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from werkzeug.security import generate_password_hash, check_password_hash

# Инициализация приложения
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Важно для работы сессий
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'flower_shop.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Определение моделей
class Product(db.Model):
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(255))
    is_bestseller = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(50), nullable=False)

class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    total = db.Column(db.Float, nullable=False)
    order_date = db.Column(db.DateTime, server_default=db.func.now())

class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)  # Переименовано для ясности

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

def initialize_database():
    with app.app_context():
        # Создаем все таблицы
        db.create_all()
        
        # Проверяем, есть ли уже данные в таблицах
        if not Product.query.first():
            # Добавляем тестовые товары
            products = [
                Product(
                    name='Роза красная',
                    description='Красные розы, 11 штук',
                    price=1500.00,
                    image='images/rose.jpg',
                    is_bestseller=True,
                    category='Букеты'
                ),
                Product(
                    name='Медведь',
                    description='Плюшевый медведь 50 см',
                    price=800.00,
                    image='images/bear.jpg',
                    category='Мягкие игрушки'
                ),
                Product(
                    name='Гелиевый шар',
                    description='Шар с гелием, 30 см',
                    price=300.00,
                    image='images/balloon.jpg',
                    category='Шарики'
                )
            ]
            db.session.bulk_save_objects(products)
        
        if not Admin.query.first():
            # Добавляем администратора с правильным хешированием пароля
            admin = Admin(username='admin')
            admin.set_password('12345')  # Используем метод установки пароля
            db.session.add(admin)
            print("Создан администратор: логин - admin, пароль - 12345")
        
        db.session.commit()
        print("База данных успешно инициализирована!")

if __name__ == '__main__':
    # Создаем папку для изображений, если ее нет
    os.makedirs(os.path.join(basedir, 'static', 'images'), exist_ok=True)
    
    # Удаляем старую базу данных, если она существует
    db_path = os.path.join(basedir, 'flower_shop.db')
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Старая база данных удалена")
    
    # Инициализируем новую базу
    initialize_database()