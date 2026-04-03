from django.contrib import admin
from django.urls import include, path

from .views import dashboard_home, home

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),
    path('core/', include('core.urls')),
    path('dashboard/', dashboard_home, name='dashboard_home'),
    path('', home, name='home'),
]
