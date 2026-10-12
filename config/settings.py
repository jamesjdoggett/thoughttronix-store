"""Django settings for the ThoughtTronix Store.

Values are read from a `.env` file at the project root via environs.
Every setting has a working default: the app runs with no `.env` present.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.0/ref/settings/
"""

from pathlib import Path

from environs import env

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env.read_env(BASE_DIR / ".env", recurse=False)

# SECURITY WARNING: the default is for development only —
# set SECRET_KEY in .env for anything beyond a laptop.
SECRET_KEY = env.str(
    "SECRET_KEY",
    default="django-insecure-your-thoughts-our-business-dev-only",
)

DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Third-party
    "django_tailwind_cli",
    # Local
    "accounts",
    "products",
    "orders",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "orders.context_processors.cart",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Authentication
# Customers are plain users; employees are is_staff; the admin is is_superuser.

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"

LOGIN_REDIRECT_URL = "products:catalog"

LOGOUT_REDIRECT_URL = "products:catalog"

# Recovery links last exactly 24 hours, as agreed in the account-security PRD.
PASSWORD_RESET_TIMEOUT = 24 * 60 * 60

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"
MEDIA_ROOT = env.path("MEDIA_ROOT", default=BASE_DIR / "media")
MEDIA_URL = env.str("MEDIA_URL", default="/media/")

STATICFILES_DIRS = [BASE_DIR / "assets"]


# Tailwind CSS + DaisyUI (django-tailwind-cli, standalone binary — no Node.js)

TAILWIND_CLI_USE_DAISY_UI = True

# Pinned tailwind-cli-extra release (bundles Tailwind CSS + DaisyUI).
TAILWIND_CLI_VERSION = "2.9.2"

TAILWIND_CLI_SRC_CSS = "assets/css/source.css"


# Email: console locally, configurable backend and sender for deployment.

EMAIL_BACKEND = env.str(
    "EMAIL_BACKEND", default="accounts.mail_backends.ConsoleEmailBackend"
)
DEFAULT_FROM_EMAIL = env.str(
    "DEFAULT_FROM_EMAIL", default="ThoughtTronix <noreply@localhost>"
)
EMAIL_HOST = env.str("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
SECURITY_EMAIL_NETWORK_LIMIT = env.int("SECURITY_EMAIL_NETWORK_LIMIT", default=30)
SECURITY_SIGNUP_LIMIT = env.int("SECURITY_SIGNUP_LIMIT", default=10)
