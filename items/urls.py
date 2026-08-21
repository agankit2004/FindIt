from django.urls import path

from . import views

app_name = "items"

urlpatterns = [
    path("", views.home, name="home"),
    path("browse/", views.item_list, name="list"),
    path("lost/", views.lost_list, name="lost"),
    path("found/", views.found_list, name="found"),
    path("report/<str:kind>/", views.report, name="report"),
    path("item/<int:pk>/", views.detail, name="detail"),
    path("item/<int:pk>/close/", views.close_item, name="close"),
    path("mine/", views.my_items, name="mine"),
    path("notifications/", views.notifications, name="notifications"),
    path("messages/", views.messages_hub, name="messages"),
]
