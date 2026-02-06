from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Home view from registry
from registry.views import home


urlpatterns = [
    # ================== Home Page ==================
    # يعرض templates/license-template/home.html
    path('', home, name='home'),

    # ================== Admin ==================
    path('admin/', admin.site.urls),

    # ================== Auth (Allauth) ==================
    # يوفر: /accounts/login/  /accounts/logout/  /accounts/microsoft/login/
    path('accounts/', include('allauth.urls')),

    # ================== Project Apps ==================
    # مسار تطبيق accounts الخاص بك (إن كان فيه صفحات/واجهات لاحقاً)
    path('app-accounts/', include('accounts.urls')),

    path('registry/', include('registry.urls')),
    path('notifications/', include('notifications.urls')),
]


# ================== Serve Media Files in Development ==================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
