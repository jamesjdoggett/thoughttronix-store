from django.urls import path

from .views import RemoveProductView, SaveProductView, WishlistView

app_name = "wishlist"

urlpatterns = [
    path("account/wishlist/", WishlistView.as_view(), name="detail"),
    path("account/wishlist/save/<int:pk>/", SaveProductView.as_view(), name="save"),
    path(
        "account/wishlist/remove/<int:pk>/", RemoveProductView.as_view(), name="remove"
    ),
]
