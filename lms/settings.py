"""
Django settings for lms project.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# ================== SECURITY ==================
SECRET_KEY = 'django-insecure-+i)$l2-$p-c1by@y(!+x8!@#absa$nmlh%!+2oowbc=$7919s6'
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]


# ================== APPLICATIONS ==================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Project Apps
    'accounts',
    'registry',
    'notifications',
]

# ✅ Custom User Model
AUTH_USER_MODEL = "accounts.User"


# ================== MIDDLEWARE ==================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'lms.urls'


# ================== TEMPLATES ==================
# ✅ templates folder location: C:\Users\404145\Projects\lms\templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # Global templates directory
        'DIRS': [BASE_DIR / 'templates'],

        # Allows app-level templates: app_name/templates/...
        'APP_DIRS': True,

        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',   # required for admin & auth
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                # Useful additions (optional but recommended)
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
            ],
        },
    },
]


WSGI_APPLICATION = 'lms.wsgi.application'


# ================== DATABASE ==================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ================== AUTH / LOGIN ==================
# لما تبني واجهة Login لاحقاً بتغير المسار لقالبك
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/admin/"


# ================== PASSWORD VALIDATION ==================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ================== INTERNATIONALIZATION ==================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ================== STATIC & MEDIA ==================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'   # useful when deploying

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ================== DEFAULT PRIMARY KEY ==================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
