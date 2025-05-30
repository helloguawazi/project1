from rest_framework import serializers
from django.contrib.auth.models import User
from .models import CmsCategory, Tag, Article, Page, Comment, MetaTag, SitemapEntry # Added MetaTag, SitemapEntry

class CmsCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CmsCategory
        fields = ['id', 'name', 'slug', 'description']
        read_only_fields = ['slug']

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']
        read_only_fields = ['slug']

class CommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True) # Display username or 'Anonymous'
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user', write_only=True, required=False, allow_null=True)

    class Meta:
        model = Comment
        fields = ['id', 'article', 'user', 'user_id', 'name', 'email', 'content', 'created_at', 'is_approved']
        read_only_fields = ['created_at', 'is_approved'] # Approval handled by admin/staff
        extra_kwargs = {
            'article': {'write_only': True}, # Article is set via URL in the view
            'name': {'required': False}, # Required only if user is not authenticated
            'email': {'required': False}, # Required only if user is not authenticated
        }

    def validate(self, data):
        # If user is not authenticated, name and email might be required (depending on settings)
        # For now, we assume they are optional if user is not set
        if not data.get('user') and not data.get('name'):
            raise serializers.ValidationError("Name is required for anonymous comments.")
        return data

class ArticleSerializer(serializers.ModelSerializer):
    categories = CmsCategorySerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    author = serializers.StringRelatedField(read_only=True)
    comments = CommentSerializer(many=True, read_only=True) # List comments related to the article

    # For write operations, allow specifying categories and tags by their IDs
    category_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=CmsCategory.objects.all(), source='categories', write_only=True, required=False
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.all(), source='tags', write_only=True, required=False
    )

    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'content', 'featured_image', 
            'categories', 'tags', 'author', 'is_published', 'is_featured',
            'comments', 'created_at', 'updated_at', 'published_at',
            'category_ids', 'tag_ids'
        ]
        read_only_fields = ('slug', 'author', 'created_at', 'updated_at', 'published_at', 'comments')

    def create(self, validated_data):
        # Author will be set in the view
        validated_data.pop('categories', None) # Remove to use category_ids
        validated_data.pop('tags', None) # Remove to use tag_ids
        categories = validated_data.pop('category_ids', [])
        tags = validated_data.pop('tag_ids', [])
        
        article = Article.objects.create(**validated_data)
        if categories:
            article.categories.set(categories)
        if tags:
            article.tags.set(tags)
        return article

    def update(self, instance, validated_data):
        validated_data.pop('categories', None)
        validated_data.pop('tags', None)
        categories = validated_data.pop('category_ids', None)
        tags = validated_data.pop('tag_ids', None)

        instance = super().update(instance, validated_data)

        if categories is not None:
            instance.categories.set(categories)
        if tags is not None:
            instance.tags.set(tags)
        return instance


class PageSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Page
        fields = ['id', 'title', 'slug', 'content', 'featured_image', 'author', 'is_published', 'created_at', 'updated_at', 'published_at']
        read_only_fields = ('slug', 'author', 'created_at', 'updated_at', 'published_at')

    def create(self, validated_data):
        # Author will be set in the view
        return Page.objects.create(**validated_data)


# SEO Serializers
from django.contrib.contenttypes.models import ContentType

class MetaTagSerializer(serializers.ModelSerializer):
    # For read operations, show the related object's string representation
    content_object_str = serializers.SerializerMethodField(read_only=True)
    
    # For write operations, allow specifying content_type by app_label.model and object_id
    # Example: {"name": "description", "content": "My page.", "content_type_model": "cms.page", "object_id": 1}
    content_type_model = serializers.CharField(write_only=True, required=False, help_text="Format: app_label.model_name (e.g., 'cms.article')")

    class Meta:
        model = MetaTag
        fields = ['id', 'name', 'content', 'content_type', 'object_id', 'content_object_str', 'content_type_model', 'created_at', 'updated_at']
        read_only_fields = ('created_at', 'updated_at', 'content_object_str')
        # Make content_type and object_id not directly required if content_type_model is used for creation/update
        extra_kwargs = {
            'content_type': {'required': False, 'write_only': True}, # Handled by content_type_model logic
            'object_id': {'required': False, 'write_only': True},    # Handled by content_type_model logic
        }

    def get_content_object_str(self, obj):
        if obj.content_object:
            return str(obj.content_object)
        return None

    def validate(self, data):
        content_type_model_str = data.pop('content_type_model', None)
        object_id = data.get('object_id', None) # object_id should be provided if content_type_model is used
        
        # If this is an update (self.instance is not None) and content_type_model is not provided,
        # we don't need to change content_type or object_id.
        if self.instance and not content_type_model_str:
            return data

        # If creating or content_type_model is provided for update
        if content_type_model_str:
            if not object_id:
                 raise serializers.ValidationError({"object_id": "Object ID is required when specifying content_type_model."})
            try:
                app_label, model_name = content_type_model_str.split('.')
                content_type = ContentType.objects.get(app_label=app_label, model=model_name)
                data['content_type'] = content_type
                # object_id is already in data if provided
            except (ContentType.DoesNotExist, ValueError):
                raise serializers.ValidationError({"content_type_model": "Invalid format or model not found. Use 'app_label.model_name'."})
        elif not self.instance: # Creating new, and no content_type_model provided
             raise serializers.ValidationError({"content_type_model": "This field is required for creating new meta tags."})
        
        # Final check for unique_together if all components are present
        name = data.get('name', self.instance.name if self.instance else None)
        ct = data.get('content_type', self.instance.content_type if self.instance else None)
        obj_id = data.get('object_id', self.instance.object_id if self.instance else None)

        if name and ct and obj_id:
            query = MetaTag.objects.filter(name=name, content_type=ct, object_id=obj_id)
            if self.instance:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise serializers.ValidationError(
                    f"A meta tag with name '{name}' already exists for this content object."
                )
        return data


class SitemapEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = SitemapEntry
        fields = ['id', 'location_url', 'last_modified', 'priority', 'change_frequency']
        read_only_fields = ('last_modified',) # last_modified is auto_now=True
