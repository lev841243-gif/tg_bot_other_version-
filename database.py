from sqlalchemy import create_engine, Column, Integer, String, BigInteger, Boolean, DateTime, Text, DECIMAL, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
import os

# Базовый класс для моделей
Base = declarative_base()


# Модели БД
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    subscription_type = Column(String(50), default='free')
    balance = Column(DECIMAL(10, 2), default=0.00)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Связь с другими таблицами
    requests = relationship("UserRequest", back_populates="user")
    payments = relationship("Payment", back_populates="user")


class UserRequest(Base):
    __tablename__ = 'user_requests'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    provider = Column(String(50))
    query = Column(Text)
    response_time = Column(Integer)
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    created_at = Column(DateTime, default=func.now())

    # Связь с пользователем
    user = relationship("User", back_populates="requests")


class Payment(Base):
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    amount = Column(DECIMAL(10, 2))
    currency = Column(String(10), default='RUB')
    status = Column(String(20), default='pending')
    provider = Column(String(50))
    payment_id = Column(String(100))
    created_at = Column(DateTime, default=func.now())

    # Связь с пользователем
    user = relationship("User", back_populates="payments")


class DatabaseManager:
    def __init__(self, database_url=None):
        self.database_url = database_url or os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/bot_db')
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Создаем таблицы
        self.create_tables()

    def create_tables(self):
        """Создает все таблицы если они не существуют"""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self):
        """Возвращает сессию БД"""
        return self.SessionLocal()

    # Оптимизированные методы для работы с пользователями
    def get_or_create_user(self, telegram_id, username=None, first_name=None, last_name=None):
        """Получает или создает пользователя ОДНИМ запросом"""
        with self.get_session() as session:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()

            if not user:
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                session.add(user)
                session.commit()
                session.refresh(user)
            else:
                # Обновляем данные если нужно
                if any([username != user.username, first_name != user.first_name, last_name != user.last_name]):
                    user.username = username
                    user.first_name = first_name
                    user.last_name = last_name
                    session.commit()

            return user

    def log_user_request(self, telegram_id, provider, query, response_time, success=True, error_message=None):
        """Логирует запрос пользователя ОДНИМ запросом с JOIN"""
        with self.get_session() as session:
            # Находим пользователя и создаем запрос в одном запросе
            user = session.query(User).filter(User.telegram_id == telegram_id).first()

            if user:
                request = UserRequest(
                    user_id=user.id,
                    provider=provider,
                    query=query,
                    response_time=response_time,
                    success=success,
                    error_message=error_message
                )
                session.add(request)
                session.commit()

    # Оптимизированные методы для аналитики
    def get_user_stats(self, days=7):
        """Получает статистику пользователей за указанный период ОДНИМ запросом"""
        with self.get_session() as session:
            from sqlalchemy import and_

            cutoff_date = datetime.now() - timedelta(days=days)

            stats = session.query(
                func.count(User.id).label('total_users'),
                func.count(UserRequest.id).label('total_requests'),
                func.avg(UserRequest.response_time).label('avg_response_time')
            ).outerjoin(
                UserRequest, and_(
                    User.id == UserRequest.user_id,
                    UserRequest.created_at >= cutoff_date
                )
            ).first()

            return {
                'total_users': stats.total_users,
                'total_requests': stats.total_requests or 0,
                'avg_response_time': float(stats.avg_response_time or 0)
            }

    def get_recent_activity(self, limit=20):
        """Получает последние действия пользователей ОДНИМ запросом с JOIN"""
        with self.get_session() as session:
            activities = session.query(
                UserRequest,
                User
            ).join(
                User, UserRequest.user_id == User.id
            ).order_by(
                UserRequest.created_at.desc()
            ).limit(limit).all()

            return [
                {
                    'user': user,
                    'request': request,
                    'timestamp': request.created_at
                }
                for request, user in activities
            ]

    def get_user_activity_report(self, telegram_id, days=30):
        """Получает полный отчет по активности пользователя ОДНИМ запросом"""
        with self.get_session() as session:
            from sqlalchemy import and_, func

            cutoff_date = datetime.now() - timedelta(days=days)

            report = session.query(
                func.count(UserRequest.id).label('total_requests'),
                func.avg(UserRequest.response_time).label('avg_response_time'),
                func.max(UserRequest.created_at).label('last_activity'),
                UserRequest.provider,
                func.count(UserRequest.provider).label('provider_count')
            ).join(
                User, UserRequest.user_id == User.id
            ).filter(
                and_(
                    User.telegram_id == telegram_id,
                    UserRequest.created_at >= cutoff_date
                )
            ).group_by(
                UserRequest.provider
            ).all()

            return [
                {
                    'provider': item.provider,
                    'request_count': item.provider_count,
                    'avg_response_time': float(item.avg_response_time or 0),
                    'last_activity': item.last_activity
                }
                for item in report
            ]


# Глобальный экземпляр менеджера БД
db = DatabaseManager()