import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-insegura')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_MODE = os.environ.get('APP_MODE', 'saas')

    # --- Flask-Mail ---
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 25))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'false').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'GestMusica <noreply@gesmusica.app>')

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
    # En desarrollo los emails se suprimen y se vuelcan en los logs
    MAIL_SUPPRESS_SEND = True
    MAIL_DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    MAIL_SUPPRESS_SEND = False

class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'postgresql://gestmusica:gestmusica_dev@localhost/gestmusica_test'
    MAIL_SUPPRESS_SEND = True
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}