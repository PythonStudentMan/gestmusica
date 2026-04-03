import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-insegura')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_MODE = os.environ.get('APP_MODE', 'saas')

    @staticmethod
    def get_database_url():
        url = os.environ.get('DATABASE_URL', '')
        # psycopg2 requiere postgresql:// en lugar de postgres://
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url

    SQLALCHEMY_DATABASE_URI = get_database_url.__func__()

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'postgresql://gestmusica:gestmusica_dev@localhost/gestmusica_test'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}