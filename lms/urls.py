from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),

    # ✅ Redirect root to registry dashboard
    path("", RedirectView.as_view(url="/registry/", permanent=False), name="root"),

    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),

    path("app-accounts/", include("accounts.urls")),
    path("registry/", include(("registry.urls", "registry"), namespace="registry")),
    path("notifications/", include("notifications.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
