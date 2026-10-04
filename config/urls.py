"""URL configuration for the ThoughtTronix Store.

Every URL is named and every app has a namespace (e.g. ``products:catalog``).
Public catalog URLs use slugs; back-office URLs use pks.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("dashboard.urls")),
    path("", include("orders.urls")),
    path("", include("products.urls")),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
