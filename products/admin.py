from django.contrib import admin
from django.utils.html import format_html

from .forms import ProductForm
from .models import Category, Product, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    readonly_fields = ("image_preview",)

    def image_preview(self, obj: Product) -> str:
        """Show the current optimized artwork or its placeholder."""
        if not obj.pk:
            return "No image yet."
        return format_html(
            '<img src="{}" width="200" class="object-contain" alt="Current product image">',
            obj.catalog_image_url,
        )

    list_display = ("name", "category", "price", "is_available")
    list_filter = ("category", "is_available", "tags")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
