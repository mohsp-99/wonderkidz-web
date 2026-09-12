from django.urls import path

from . import views

app_name = "payments"
urlpatterns = [
    path("plans/", views.plans, name="plans"),
    path("start/<int:plan_id>/", views.start, name="start"),
    path("callback/", views.callback, name="callback"),
    path("fake/<int:pk>/", views.fake_gateway_page, name="fake_gateway"),
    path("<int:pk>/result/", views.result, name="result"),
]
