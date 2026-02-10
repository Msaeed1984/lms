"""
Django settings for lms project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# ================== BASE DIR ==================
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(BASE_DIR / ".env")


# ================== SECURITY ==================
# ✅ الأفضل: خزن SECRET_KEY في متغير بيئة بالإنتاج
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-+i)$l2-$p-c1by@y(!+x8!@#absa$nmlh%!+2oowbc=$7919s6",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("1", "true", "yes")

# ✅ في التطوير محلياً
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# ✅ إذا شغلت على دومين/سيرفر لاحقاً (مثال):
# ALLOWED_HOSTS += ["your-domain.com", "www.your-domain.com"]


# ================== APPLICATIONS ==================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # ✅ Required for allauth
    "django.contrib.sites",

    # ✅ Cloudinary (Media Storage)
    "cloudinary",
    "cloudinary_storage",

    # ✅ Allauth Core
    "allauth",
    "allauth.account",
    "allauth.socialaccount",

    # ✅ Microsoft Provider (Azure AD)
    "allauth.socialaccount.providers.microsoft",

    # ✅ Project Apps
    "accounts",
    "registry",
    "notifications",
]

# ✅ Custom User Model
AUTH_USER_MODEL = "accounts.User"


# ================== ALLAUTH CONFIG ==================
SITE_ID = 1

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

# ✅ Auth URLs (keep exactly as you had to avoid breaking flow)
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"              # ✅ keep as-is (safe)
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ✅ Login by Username OR Email
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "none"

# ✅ No self registration (Admin only)
ACCOUNT_ALLOW_REGISTRATION = False

# ✅ Remember session (optional)
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGOUT_ON_GET = False

# ✅ Prevent auto-creating users from Microsoft login
SOCIALACCOUNT_AUTO_SIGNUP = False

# ✅ Microsoft provider minimal settings (safe)
SOCIALACCOUNT_PROVIDERS = {
    "microsoft": {
        "SCOPE": ["openid", "email", "profile", "User.Read"],
        "AUTH_PARAMS": {"prompt": "select_account"},
    }
}


# ================== MIDDLEWARE ==================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.locale.LocaleMiddleware",  # للغات

    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "allauth.account.middleware.AccountMiddleware",  # ✅ required

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ================== URLS / WSGI ==================
ROOT_URLCONF = "lms.urls"
WSGI_APPLICATION = "lms.wsgi.application"


# ================== TEMPLATES ==================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",  # ✅ required for admin & allauth
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",

                # Optional but useful
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
            ],
        },
    },
]


# ================== DATABASE ==================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ================== PASSWORD VALIDATION ==================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ================== INTERNATIONALIZATION ==================
LANGUAGE_CODE = "en"
USE_I18N = True

LANGUAGES = [
    ("en", "English"),
    ("ar", "العربية"),
]

TIME_ZONE = "UTC"   # ✅ keep as-is (safe)
USE_TZ = True

LANGUAGE_COOKIE_NAME = "django_language"


# ================== STATIC & MEDIA ==================
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# ✅ MEDIA: سيتم تخزين الملفات على Cloudinary عبر DEFAULT_FILE_STORAGE
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"  # لن تُستخدم فعلياً مع Cloudinary، لكن لا ضرر من إبقائها

# ✅ Upload limits (safe, helps image/pdf attachments)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024      # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024     # 10MB


# ================== CLOUDINARY (MEDIA STORAGE) ==================
# ✅ ضع القيم في .env:
# CLOUDINARY_CLOUD_NAME=...
# CLOUDINARY_API_KEY=...
# CLOUDINARY_API_SECRET=...
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    "API_KEY": os.environ.get("CLOUDINARY_API_KEY", ""),
    "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET", ""),
    "SECURE": True,  # يقدم روابط https
}

# ✅ اجعل Cloudinary هو مخزن الميديا الافتراضي
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"


# ================== EMAIL (Office 365 SMTP) ==================
# ✅ ضع كلمة المرور في متغير بيئة: EMAIL_HOST_PASSWORD
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.office365.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "zms@emsteel.com")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")

# From/Reply-to الافتراضي
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "Visitor Arrival Notification <zms@emsteel.com>",
)
SERVER_EMAIL = EMAIL_HOST_USER

# ✅ اختياري: مهلة الإرسال (ثواني)
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "20"))


# ================== SECURITY HEADERS (SAFE DEFAULTS) ==================
# These won't break local development because DEBUG=True => secure cookies False.
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# ✅ مهم عند النشر خلف Reverse Proxy/HTTPS (فعّله عند الحاجة)
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ✅ إذا نشرت على دومين https وتكرر CSRF 403، أضف الدومين هنا:
# CSRF_TRUSTED_ORIGINS = [
#     "https://your-domain.com",
#     "https://www.your-domain.com",
# ]


# ================== LOGGING (Helpful for Notification Engine) ==================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO" if not DEBUG else "DEBUG",
    },
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "notifications": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}


# ================== DEFAULT PRIMARY KEY ==================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
