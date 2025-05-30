from django import forms
from .models import Category, Product, ProductImage, ProductAttribute

class CategoryForm(forms.ModelForm):
    parent = forms.ModelChoiceField(
        queryset=Category.objects.all(), 
        required=False, 
        widget=forms.Select(attrs={'class': 'form-control select2'}),
        help_text="Select a parent to create a sub-category. Leave blank for a top-level category."
    )

    class Meta:
        model = Category
        fields = ['name', 'slug', 'parent', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        help_texts = {
            'slug': 'If blank, the slug will be auto-generated from the name.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # To prevent a category from being its own parent or a child of its descendants
        if self.instance and self.instance.pk:
            # Get all descendants of the current category instance
            descendants = self._get_all_descendants(self.instance)
            # Exclude the instance itself and its descendants from the parent choices
            self.fields['parent'].queryset = Category.objects.exclude(
                pk__in=[self.instance.pk] + [desc.pk for desc in descendants]
            )
        else:
            # For new categories, no instance yet, so all categories are valid parents
            self.fields['parent'].queryset = Category.objects.all()
            
    def _get_all_descendants(self, category):
        descendants = []
        children = category.children.all()
        for child in children:
            descendants.append(child)
            descendants.extend(self._get_all_descendants(child))
        return descendants


class ProductForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control select2'}),
        label="Category"
    )
    description = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control summernote'}), required=False)

    class Meta:
        model = Product
        fields = ['name', 'slug', 'category', 'description', 'price', 'stock', 'available']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'slug': 'If blank, the slug will be auto-generated from the name.',
        }


class ProductImageForm(forms.ModelForm):
    image = forms.ImageField(widget=forms.ClearableFileInput(attrs={'class': 'form-control-file'}), required=True)
    caption = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control mt-2'}), required=False)
    
    class Meta:
        model = ProductImage
        fields = ['image', 'caption']


class ProductAttributeForm(forms.ModelForm):
    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Color'}))
    value = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Red'}))

    class Meta:
        model = ProductAttribute
        fields = ['name', 'value']
