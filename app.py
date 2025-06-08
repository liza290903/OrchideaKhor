from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import event
from sqlalchemy.engine import Engine
import os
from datetime import datetime
from flask_wtf.csrf import CSRFProtect
import uuid 
from flask import session
import json # Для генерации уникальных имен файлов

# Инициализация приложения
app = Flask(__name__)
app.secret_key = 'xK6$8pL2#qF5!sW3*eR6%tY1@uI7^oP4&jK0(lO9)nM8_mN7-bV5='
csrf = CSRFProtect(app)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'flower_shop.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'images')
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png', 'webp'}

db = SQLAlchemy(app)

# Модели
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(255))
    is_bestseller = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Связь с OrderItem через back_populates
    order_items = db.relationship(
        'OrderItem',
        back_populates='product',
        cascade='all, delete-orphan',
        passive_deletes=True
    )


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    total = db.Column(db.Float, nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Новый')

    # Связь с OrderItem
    items = db.relationship(
        'OrderItem',
        backref='order',
        cascade='all, delete-orphan',
        passive_deletes=True
    )


class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    # Обратная связь с Product
    product = db.relationship('Product', back_populates='order_items')



# Вспомогательные функции
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@app.before_request
@csrf.exempt
def setup_cart():
    if 'cart' not in session or not isinstance(session['cart'], dict):
        session['cart'] = {}  # Инициализируем как пустой словарь

# Маршруты
@app.route('/')
@csrf.exempt
def index():
    bestsellers = Product.query.filter_by(is_bestseller=True).limit(4).all()
    return render_template('index.html', bestsellers=bestsellers, page='home')



@app.route('/catalog')
@csrf.exempt
def catalog():
    category = request.args.get('category', 'Букеты')  # Значение по умолчанию
    
    # Фильтрация товаров
    if category == 'all':
        products = Product.query.order_by(Product.created_at.desc()).all()
    else:
        products = Product.query.filter_by(category=category)\
                      .order_by(Product.created_at.desc()).all()
    
    return render_template('catalog.html', 
                         products=products,
                         category=category)

@app.route('/cart')
@csrf.exempt
def cart():
    cart_items = []
    total = 0
    
    if 'cart' in session and isinstance(session['cart'], dict):
        cart_items = [{'id': pid, **data} for pid, data in session['cart'].items()]
        total = sum(item['price'] * item['quantity'] for item in cart_items)
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/order', methods=['GET', 'POST'])
@csrf.exempt
def order():
    if 'cart' not in session or not session['cart']:
        return redirect(url_for('cart'))
    
    if request.method == 'POST':
        try:
            # Создаем новый заказ
            new_order = Order(
                customer_name=request.form.get('name'),
                phone=request.form.get('phone'),
                address=request.form.get('address'),
                total=sum(item['price'] * item.get('quantity', 1) for item in session['cart'].values())
            )
            db.session.add(new_order)
            db.session.flush()  # Получаем ID заказа
            
            # Добавляем товары в заказ
            for product_id, item in session['cart'].items():
                product = db.session.get(Product, product_id)
                if product:
                    order_item = OrderItem(
                        order_id=new_order.id,
                        product_id=product.id,
                        quantity=item.get('quantity', 1)
                    )
                    db.session.add(order_item)
            
            db.session.commit()
            session.pop('cart', None)
            flash('Заказ успешно оформлен! Спасибо!', 'success')
            return redirect(url_for('index'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при оформлении заказа: {str(e)}', 'danger')
            return redirect(url_for('order'))
    
    total = sum(item['price'] * item.get('quantity', 1) for item in session['cart'].values())
    return render_template('order.html', total=total)

# Админ-панель
@app.route('/admin/login', methods=['GET', 'POST'])
@csrf.exempt
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Вы успешно вошли в систему', 'success')
            return redirect(url_for('admin_panel'))
        else:
            flash('Неверные учетные данные', 'danger')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
@csrf.exempt
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/admin', endpoint='admin_panel')
@csrf.exempt
def admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    try:
        products = db.session.query(Product).order_by(Product.id.desc()).all()
        orders = db.session.query(Order).order_by(Order.order_date.desc()).all()
        return render_template('admin.html', products=products, orders=orders)
    except Exception as e:
        flash(f'Ошибка при загрузке админ-панели: {str(e)}', 'danger')
        return redirect(url_for('index'))



@app.route('/admin/add_product', methods=['POST'])
@csrf.exempt
def add_product():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    # Обработка изображения
    if 'image' not in request.files:
        flash('Не выбрано изображение товара', 'danger')
        return redirect(url_for('admin_panel'))

    file = request.files['image']
    if file.filename == '':
        flash('Не выбрано изображение товара', 'danger')
        return redirect(url_for('admin_panel'))

    if not (file and allowed_file(file.filename)):
        flash('Недопустимый формат изображения', 'danger')
        return redirect(url_for('admin_panel'))

    # Создаем папку для загрузок, если ее нет
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Генерируем уникальное имя файла
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    
    try:
        file.save(filepath)
        
        # Создаем товар
        product = Product(
            name=request.form['name'],
            description=request.form.get('description', ''),
            price=float(request.form['price']),
            image=f'images/{unique_filename}',
            is_bestseller=bool(request.form.get('is_bestseller')),
            category=request.form['category']
        )
        
        db.session.add(product)
        db.session.commit()
        flash('Товар успешно добавлен', 'success')
    except Exception as e:
        # Удаляем файл, если не удалось сохранить товар
        if os.path.exists(filepath):
            os.remove(filepath)
        db.session.rollback()
        flash(f'Ошибка при добавлении товара: {str(e)}', 'danger')
    
    return redirect(url_for('admin_panel'))

@app.route('/admin/edit_product/<int:id>', methods=['GET'])
@csrf.exempt
def edit_product_form(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    product = db.session.get(Product, id)
    if not product:
        flash('Товар не найден', 'danger')
        return redirect(url_for('admin_panel'))
    
    return render_template('admin/edit_product.html', product=product)

@app.route('/admin/update_product/<int:id>', methods=['POST'])
@csrf.exempt
def update_product(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    product = db.session.get(Product, id)
    if not product:
        flash('Товар не найден', 'danger')
        return redirect(url_for('admin_panel'))

    try:
        # Обновляем основные данные
        product.name = request.form['name']
        product.description = request.form.get('description', '')
        product.price = float(request.form['price'])
        product.category = request.form['category']
        product.is_bestseller = 'is_bestseller' in request.form
        
        # Обновляем изображение, если загружено новое
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '' and allowed_file(file.filename):
                # Удаляем старое изображение
                if product.image:
                    old_path = os.path.join(app.static_folder, product.image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Сохраняем новое изображение
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                product.image = f'images/{unique_filename}'
        
        db.session.commit()
        flash('Товар успешно обновлен', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении товара: {str(e)}', 'danger')
    
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_product/<int:id>', methods=['POST'])
@csrf.exempt
def delete_product(id):
    if not session.get('admin_logged_in'):
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('admin_login'))

    product = Product.query.get_or_404(id)
    
    try:
        # Удаляем изображение товара
        if product.image:
            image_path = os.path.join(app.static_folder, product.image)
            if os.path.exists(image_path):
                os.remove(image_path)
        
        db.session.delete(product)
        db.session.commit()
        flash('Товар успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении товара: {str(e)}', 'danger')
    
    return redirect(url_for('admin_panel'))

@app.route('/admin/toggle_bestseller/<int:id>', methods=['POST'])
@csrf.exempt
def toggle_bestseller(id):
    if not session.get('admin_logged_in'):
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('admin_login'))

    product = db.session.get(Product, id)
    if product:
        try:
            product.is_bestseller = not product.is_bestseller
            db.session.commit()
            flash(f'Товар {"добавлен в хиты" if product.is_bestseller else "удален из хитов"}', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при изменении статуса товара: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('admin_panel'))

@app.route('/remove_from_cart/<string:item_id>', methods=['POST'])
@csrf.exempt
def remove_from_cart(item_id):
    if 'cart' not in session or not isinstance(session['cart'], dict):
        return jsonify({'success': False, 'error': 'Корзина не найдена'})
    
    try:
        if item_id in session['cart']:
            # Удаляем товар полностью
            del session['cart'][item_id]
            session.modified = True
            
            # Пересчитываем общую сумму
            total = sum(item['price'] * item['quantity'] for item in session['cart'].values())
            
            return jsonify({
                'success': True,
                'cart_count': sum(item['quantity'] for item in session['cart'].values()),
                'new_total': total
            })
        return jsonify({'success': False, 'error': 'Товар не найден'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/clear_cart', methods=['POST'])
@csrf.exempt
def clear_cart():
    if 'cart' in session:
        session.pop('cart')
        flash('Корзина очищена', 'success')
    return redirect(url_for('cart'))

@app.route('/add_to_cart_ajax', methods=['POST'])
@csrf.exempt
def add_to_cart_ajax():
    if request.method == 'POST':
        data = request.get_json()
        
        if 'cart' not in session or not isinstance(session['cart'], dict):
            session['cart'] = {}
        
        product_id = str(data['product_id'])
        
        # Добавление/обновление товара
        if product_id in session['cart']:
            session['cart'][product_id]['quantity'] += 1
        else:
            session['cart'][product_id] = {
                'name': data['name'],
                'price': data['price'],
                'image': data['image'],
                'quantity': 1
            }
        
        session.modified = True
        
        return jsonify({
            'success': True,
            'cart_count': sum(item['quantity'] for item in session['cart'].values())
        })
    
    return jsonify({'success': False})

@app.route('/add_to_cart', methods=['POST'])
@csrf.exempt
def add_to_cart():
    try:
        data = request.get_json()
        product_id = str(data['product_id'])
        
        # Инициализация корзины, если ее нет
        if 'cart' not in session or not isinstance(session['cart'], dict):
            session['cart'] = {}
        
        # Добавление/обновление товара
        if product_id in session['cart']:
            session['cart'][product_id]['quantity'] += 1
        else:
            session['cart'][product_id] = {
                'name': data['name'],
                'price': float(data['price']),
                'image': data['image'],
                'quantity': 1
            }
        
        session.modified = True
        return jsonify({
            'success': True,
            'cart_count': sum(item['quantity'] for item in session['cart'].values())
        })
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': str(e)
        })

@app.route('/contacts')
@csrf.exempt
def contacts():
    return render_template('contacts.html')

@app.route('/admin/orders')
@csrf.exempt
def admin_orders():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    orders = Order.query.order_by(Order.order_date.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/view_order/<int:order_id>')
@csrf.exempt
def view_order(order_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    order = Order.query.get_or_404(order_id)
    return render_template('admin/order_details.html', order=order)

@app.route('/admin/update_order_status/<int:order_id>/<status>', methods=['POST'])
@csrf.exempt
def update_order_status(order_id, status):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    order = Order.query.get_or_404(order_id)
    
    if status == 'completed':
        order.status = 'Выполнен'
    elif status == 'cancelled':
        order.status = 'Отменен'
    
    try:
        db.session.commit()
        flash('Статус заказа обновлен', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении статуса: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('admin_panel'))

@app.route('/admin/all_orders')
@csrf.exempt
def all_orders():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    # Получаем все заказы, отсортированные по дате (новые сначала)
    orders = Order.query.order_by(Order.order_date.desc()).all()
    
    return render_template('admin/all_orders.html', 
                         orders=orders,
                         order_statuses=['Новый', 'В обработке', 'Выполнен', 'Отменен'])

@app.route('/admin/delete_order/<int:order_id>', methods=['POST'])
@csrf.exempt
def delete_order(order_id):
    if not session.get('admin_logged_in'):
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('admin_login'))

    order = Order.query.get_or_404(order_id)

    try:
        db.session.delete(order)
        db.session.commit()
        flash('Заказ успешно удалён', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении заказа: {str(e)}', 'danger')

    return redirect(url_for('admin_panel', tab='orders'))

@app.route('/about')
@csrf.exempt
def about():
    return render_template('about.html')

if __name__ == '__main__':
    with app.app_context():
        # Создаем папку для загрузок, если ее нет
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        # Создаем таблицы, если их нет
        db.create_all()
        
        # Создаем администратора, если его нет
        if not Admin.query.first():
            admin = Admin(username='admin')
            admin.set_password('12345')
            db.session.add(admin)
            db.session.commit()
            print('Создан администратор: логин - admin, пароль - 12345')
    
    app.run(debug=True)