from django.contrib import admin

from .models import (
    CommitteeCategory,
    CommitteeMember,
    Competition,
    CompetitionDetail,
    CompetitionTag,
    FAQ,
    Game,
    Guest,
    HeroChip,
    PersonReview,
    Review,
    SiteSetting,
    Sponsor,
    Stat,
    TickerItem,
    TimelineStep,
)


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Brand", {"fields": ("site_name", "org_name", "tagline")}),
        ("Hero", {"fields": ("hero_kicker", "hero_title_line1", "hero_title_line2", "hero_subtitle")}),
        ("Event", {"fields": ("event_date", "venue_name", "venue_address", "participants_label")}),
        ("About", {"fields": ("about_heading_a", "about_heading_b", "about_para1", "about_para2")}),
        ("CTA", {"fields": ("cta_tag", "cta_title_a", "cta_title_b", "cta_subtitle")}),
        ("Campus Ambassador", {"fields": ("ca_heading", "ca_description", "ca_open")}),
        ("Contact & Footer", {"fields": ("contact_email", "facebook_url", "footer_about", "made_by_name", "made_by_url")}),
        ("SEO / Social", {"fields": ("meta_description", "og_image_url")}),
        ("Switches", {"fields": ("register_status",)}),
        ("Meta", {"fields": ("committee_note",)}),
    )

    def has_add_permission(self, request):
        # Singleton — only ever edited, never added/deleted.
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HeroChip)
class HeroChipAdmin(admin.ModelAdmin):
    list_display = ("html", "css_class", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(TickerItem)
class TickerItemAdmin(admin.ModelAdmin):
    list_display = ("html", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(Stat)
class StatAdmin(admin.ModelAdmin):
    list_display = ("label", "value", "suffix", "order")
    list_editable = ("value", "suffix", "order")


class CompetitionTagInline(admin.TabularInline):
    model = CompetitionTag
    extra = 1


class CompetitionDetailInline(admin.TabularInline):
    model = CompetitionDetail
    extra = 1


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "order", "is_active")
    list_editable = ("order", "is_active")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CompetitionTagInline, CompetitionDetailInline]


@admin.register(TimelineStep)
class TimelineStepAdmin(admin.ModelAdmin):
    list_display = ("step_no", "title", "tag", "order")
    list_editable = ("order",)


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "is_featured", "order", "is_active")
    list_filter = ("is_featured", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("name", "role")


class CommitteeMemberInline(admin.TabularInline):
    model = CommitteeMember
    extra = 1
    fields = ("name", "role", "image_url", "order", "is_active")


@admin.register(CommitteeCategory)
class CommitteeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CommitteeMemberInline]


@admin.register(CommitteeMember)
class CommitteeMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "category", "order", "is_active")
    list_filter = ("category", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("name", "role")


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    list_display = ("name", "is_surprise", "order", "is_active")
    list_editable = ("is_surprise", "order", "is_active")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "order", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("question",)


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "difficulty", "order", "is_active")
    list_editable = ("order", "is_active")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "rating", "is_approved", "updated_at")
    list_filter = ("rating", "is_approved")
    list_editable = ("is_approved",)
    search_fields = ("user__username", "comment")
    actions = ["approve_reviews", "unapprove_reviews"]

    @admin.action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description="Hide selected reviews")
    def unapprove_reviews(self, request, queryset):
        queryset.update(is_approved=False)


@admin.register(PersonReview)
class PersonReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "target_name", "rating", "is_approved", "updated_at")
    list_filter = ("rating", "is_approved")
    list_editable = ("is_approved",)
    search_fields = (
        "user__username",
        "comment",
        "volunteer__name",
        "ambassador__full_name",
    )
    actions = ["approve_reviews", "unapprove_reviews"]

    @admin.display(description="Volunteer / Ambassador")
    def target_name(self, obj):
        return str(obj.target)

    @admin.action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description="Hide selected reviews")
    def unapprove_reviews(self, request, queryset):
        queryset.update(is_approved=False)
