from django.urls import path

from . import views

app_name = "panel"
urlpatterns = [
    path("", views.queue, name="queue"),
    path("listing/<int:pk>/approve/", views.approve, name="approve"),
    path("listing/<int:pk>/reject/", views.reject, name="reject"),
    path("reports/", views.reports, name="reports"),
    path("reports/<int:pk>/resolve/", views.resolve_report, name="resolve_report"),
    path("users/", views.users, name="users"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/ban/", views.ban_user, name="ban_user"),
    path("listings/", views.listings, name="listings"),
    path("listings/<int:pk>/takedown/", views.takedown, name="takedown"),
    path("stats/", views.stats, name="stats"),
    path("decisions/", views.decisions, name="decisions"),
]
