from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("django-admin/", admin.site.urls),

    path("", include("accounts.urls")),                 # login/logout/go
    path("Administration/", include("gestion.urls")),   # backoffice superadmin
    path("Responsable/", include("responsable.urls")),  # espace responsable
    path("Etudiant/", include("etudiant.urls")),        # espace étudiant
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

