from django.urls import path

from .views import (
    AddSavedProductToCartView,
    DisableSharingView,
    EnableSharingView,
    RemoveProductView,
    SaveProductView,
    SharedWishlistView,
    WishlistView,
)

app_name = "wishlist"

urlpatterns = [
    path(
        "account/wishlist/sharing/enable/",
        EnableSharingView.as_view(),
        name="enable_sharing",
    ),
    path(
        "account/wishlist/sharing/disable/",
        DisableSharingView.as_view(),
        name="disable_sharing",
    ),
    path("wishlists/shared/<str:token>/", SharedWishlistView.as_view(), name="shared"),
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
