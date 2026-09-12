from django.urls import path

from . import views

app_name = "listings"
urlpatterns = [
    path("", views.home, name="home"),
    path("s/", views.search, name="search"),
    path("s/<str:category_slug>/", views.search, name="category"),
    path("s/<str:category_slug>/<str:district_slug>/", views.search, name="category_district"),
    path("v/<str:code>/", views.detail, name="detail_short"),
    path("v/<str:code>/reveal/", views.reveal_phone, name="reveal"),
    path("v/<str:code>/save/", views.toggle_save, name="save"),
    path("v/<str:code>/report/", views.report, name="report"),
    path("v/<str:code>/sold/", views.mark_sold, name="mark_sold"),
    path("v/<str:code>/renew/", views.renew, name="renew"),
    path("v/<str:code>/delete/", views.delete, name="delete"),
    path("v/<str:code>/edit/", views.edit, name="edit"),
    path("v/<str:code>/<str:slug>/", views.detail, name="detail"),
    path("new/", views.post, name="post"),
    path("new/upload/", views.upload_image, name="upload_image"),
    path("new/image/<int:pk>/delete/", views.delete_image, name="delete_image"),
    path("save-search/", views.save_search, name="save_search"),
    path("p/<str:slug>/", views.page, name="page"),
]
