from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Home view from registry
from registry.views import home


urlpatterns = [
    # ================== Language Switch (IMPORTANT) ==================
    path("i18n/", include("django.conf.urls.i18n")),

    # ================== Home Page ==================
    path('', home, name='home'),

    # ================== Admin ==================
    path('admin/', admin.site.urls),

    # ================== Auth (Allauth) ==================
    path('accounts/', include('allauth.urls')),

    # ================== Project Apps ==================
    path('app-accounts/', include('accounts.urls')),
    path('registry/', include('registry.urls')),
    path('notifications/', include('notifications.urls')),
]

# ================== Serve Media Files in Development ==================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
