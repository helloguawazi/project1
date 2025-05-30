from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User
from decimal import Decimal # For SitemapEntry priority choices

# CMS Specific Category
class CmsCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "CMS Category"
        verbose_name_plural = "CMS Categories"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

# Tag Model
class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

# Article Model
class Article(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    content = models.TextField()
    featured_image = models.ImageField(upload_to='article_featured_images/', null=True, blank=True)
    categories = models.ManyToManyField(CmsCategory, related_name='articles', blank=True)
    tags = models.ManyToManyField(Tag, related_name='articles', blank=True)
    author = models.ForeignKey(User, related_name='articles', on_delete=models.SET_NULL, null=True)
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False) # To list featured articles
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True) # Can be set when is_published is True

    class Meta:
        ordering = ['-published_at', '-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            # Create a unique slug if multiple articles have the same title
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            # Check for uniqueness
            while Article.objects.filter(slug=slug).exists() and (self.pk is None or Article.objects.get(pk=self.pk).slug != slug) :
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if self.is_published and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

# Page Model (Simplified version, could be extended)
class Page(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    content = models.TextField()
    featured_image = models.ImageField(upload_to='page_featured_images/', null=True, blank=True)
    author = models.ForeignKey(User, related_name='pages', on_delete=models.SET_NULL, null=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['title']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Page.objects.filter(slug=slug).exists() and (self.pk is None or Page.objects.get(pk=self.pk).slug != slug):
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if self.is_published and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

# Comment Model for Articles
class Comment(models.Model):
    article = models.ForeignKey(Article, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='comments', on_delete=models.CASCADE, null=True, blank=True) # User can be nullable if anonymous comments are allowed
    name = models.CharField(max_length=100, blank=True) # Name for anonymous comments
    email = models.EmailField(blank=True) # Email for anonymous comments
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=True) # Basic moderation

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.user.username if self.user else self.name} on {self.article.title}"


# SEO Related Models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class MetaTag(models.Model):
    """
    Meta tags for SEO, attachable to any model using GenericForeignKey.
    """
    name = models.CharField(max_length=255, help_text="e.g., 'description', 'keywords', 'og:title'")
    content = models.TextField(help_text="The value of the meta tag.")
    
    # Generic Foreign Key to allow linking to any model instance
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        # Ensure a specific meta tag name is unique per content object
        unique_together = ('name', 'content_type', 'object_id') 
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.name}: {self.content[:50]}... (for {self.content_object})"


class SitemapEntry(models.Model):
    """
    Represents an entry in a sitemap.
    This could be auto-generated or manually managed.
    For simplicity, this model allows manual entries or could be populated by a script.
    """
    LOCATION_PRIORITY_CHOICES = [
        (Decimal('0.1'), '0.1'), (Decimal('0.2'), '0.2'), (Decimal('0.3'), '0.3'), (Decimal('0.4'), '0.4'),
        (Decimal('0.5'), '0.5 (Default)'), (Decimal('0.6'), '0.6'), (Decimal('0.7'), '0.7'), 
        (Decimal('0.8'), '0.8'), (Decimal('0.9'), '0.9'), (Decimal('1.0'), '1.0 (Highest)'),
    ]
    CHANGE_FREQUENCY_CHOICES = [
        ('always', 'Always'), ('hourly', 'Hourly'), ('daily', 'Daily'),
        ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('yearly', 'Yearly'),
        ('never', 'Never'),
    ]

    location_url = models.CharField(max_length=2000, unique=True, help_text="Absolute URL of the page. E.g., /products/my-product-slug or https://example.com/about")
    last_modified = models.DateTimeField(auto_now=True, help_text="Last modification date of the content at this URL.")
    priority = models.DecimalField(
        max_digits=2, decimal_places=1, 
        choices=LOCATION_PRIORITY_CHOICES, default=Decimal('0.5')
    )
    change_frequency = models.CharField(
        max_length=10, choices=CHANGE_FREQUENCY_CHOICES, default='weekly'
    )
    
    # Optional: Link to a specific content object if the sitemap entry corresponds to one
    # content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    # object_id = models.PositiveIntegerField(null=True, blank=True)
    # content_object = GenericForeignKey('content_type', 'object_id')


    class Meta:
        verbose_name = "Sitemap Entry"
        verbose_name_plural = "Sitemap Entries"
        ordering = ['-priority', '-last_modified']

    def __str__(self):
        return f"{self.location_url} (Priority: {self.priority}, Freq: {self.change_frequency})"
