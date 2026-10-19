from django.urls import path

from .views import (
    AddSavedProductToCartView,
    RemoveProductView,
    SaveProductView,
    WishlistView,
)

app_name = "wishlist"

urlpatterns = [
    path("account/wishlist/", WishlistView.as_view(), name="detail"),
    path(
        "account/wishlist/cart/<int:pk>/",
        AddSavedProductToCartView.as_view(),
        name="add_to_cart",
    ),
    path("account/wishlist/save/<int:pk>/", SaveProductView.as_view(), name="save"),
    path(
        "account/wishlist/remove/<int:pk>/", RemoveProductView.as_view(), name="remove"
    ),
]
