from django.contrib import admin

from .models import Comment, Like, Post


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ("author", "body", "created_at")
    can_delete = True


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "status", "published_at", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "excerpt", "content")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = [CommentInline]

    def save_model(self, request, obj, form, change):
        if not change or not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("post", "author", "is_approved", "created_at")
    list_filter = ("is_approved",)
    list_editable = ("is_approved",)
    search_fields = ("body", "author__username", "post__title")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "created_at")
    search_fields = ("post__title", "user__username")

    def has_add_permission(self, request):
        return False
