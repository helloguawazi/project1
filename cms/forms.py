from django import forms
from .models import CmsCategory, Tag, Article, Page, Comment

# CMS Category Form
class CmsCategoryForm(forms.ModelForm):
    class Meta:
        model = CmsCategory
        fields = ['name', 'slug', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        help_texts = {
            'slug': 'If blank, the slug will be auto-generated from the name.',
        }

# Tag Form
class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'slug': 'If blank, the slug will be auto-generated from the name.',
        }

# Article Form
class ArticleForm(forms.ModelForm):
    content = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control summernote'}), required=False)
    categories = forms.ModelMultipleChoiceField(
        queryset=CmsCategory.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2', 'multiple': 'multiple'}),
        required=False
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2', 'multiple': 'multiple'}),
        required=False
    )
    featured_image = forms.ImageField(widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'}), required=False)

    class Meta:
        model = Article
        fields = [
            'title', 'slug', 'content', 'featured_image', 'categories', 'tags', 
            'is_published', 'is_featured', 'published_at'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'published_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }
        help_texts = {
            'slug': 'If blank, the slug will be auto-generated from the title.',
            'published_at': 'Set this to schedule future publishing. If "Is Published" is checked and this is blank, it will be set to now.',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing, published_at might have a value. Format it correctly for the widget.
        if self.instance and self.instance.published_at:
            self.initial['published_at'] = self.instance.published_at.strftime('%Y-%m-%dT%H:%M')
        elif not self.instance: # For new articles, if is_published is True, default published_at to now
             self.initial['published_at'] = '' # Keep it blank initially

# Page Form
class PageForm(forms.ModelForm):
    content = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control summernote'}), required=False)
    featured_image = forms.ImageField(widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'}), required=False)

    class Meta:
        model = Page
        fields = ['title', 'slug', 'content', 'featured_image', 'is_published', 'published_at']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'published_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }
        help_texts = {
            'slug': 'If blank, the slug will be auto-generated from the title.',
            'published_at': 'Set this to schedule future publishing. If "Is Published" is checked and this is blank, it will be set to now.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.published_at:
            self.initial['published_at'] = self.instance.published_at.strftime('%Y-%m-%dT%H:%M')
        elif not self.instance:
             self.initial['published_at'] = ''


# Comment Form (Basic - for admin moderation if needed, not for frontend user submission)
class CommentAdminForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['user', 'name', 'email', 'content', 'is_approved', 'article']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-control select2'}),
            'article': forms.Select(attrs={'class': 'form-control select2'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_approved': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make user and article read-only or selectable if admin is creating a comment manually
        # For editing, they usually shouldn't be changed.
        if self.instance and self.instance.pk:
            self.fields['user'].disabled = True
            self.fields['article'].disabled = True
