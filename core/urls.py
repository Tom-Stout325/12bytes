from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("onboarding/", views.onboarding, name="onboarding"),
]
