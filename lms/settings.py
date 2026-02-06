"""
Django settings for lms project.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# ================== SECURITY ==================
SECRET_KEY = "django-insecure-+i)$l2-$p-c1by@y(!+x8!@#absa$nmlh%!+2oowbc=$7919s6"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]


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

# ✅ Auth URLs
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
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


# ================== MIDDLEWARE ==================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # ✅ Required by allauth

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ================== URLS / WSGI ==================
ROOT_URLCONF = "lms.urls"
WSGI_APPLICATION = "lms.wsgi.application"


# ================== TEMPLATES ==================
# Global templates directory: C:\Users\404145\Projects\lms\templates
# Example template path: templates/license-template/home.html
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
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ================== STATIC & MEDIA ==================
# Static files: put your files inside BASE_DIR/static
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# collectstatic output (for deployment)
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media uploads (attachments, images, pdf...)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# ================== DEFAULT PRIMARY KEY ==================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
