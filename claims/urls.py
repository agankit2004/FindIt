from django.urls import path

from . import views

app_name = "claims"

urlpatterns = [
    path("", views.my_claims, name="mine"),
    path("new/<int:item_pk>/", views.create, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/advance/", views.advance, name="advance"),
    path("<int:pk>/message/", views.post_message, name="message"),
    path("<int:pk>/handover/", views.set_handover, name="handover"),
]
