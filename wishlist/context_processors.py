from .models import WishlistEntry


def wishlist(request):
    return {
        "wishlist_item_count": (
            WishlistEntry.objects.filter(wishlist__user=request.user).count()
            if request.user.is_authenticated
            else 0
        )
    }
