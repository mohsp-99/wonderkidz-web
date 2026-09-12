from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("login/verify/", views.verify_view, name="verify"),
    path("login/resend/", views.resend_view, name="resend"),
    path("logout/", views.logout_view, name="logout"),
    path("me/", views.profile_view, name="profile"),
    path("me/account/", views.account_edit_view, name="account_edit"),
    path("me/saved-search/<int:pk>/delete/", views.saved_search_delete, name="saved_search_delete"),
    path("set-city/", views.set_city, name="set_city"),
    path("u/<int:pk>/", views.public_profile_view, name="public_profile"),
]
