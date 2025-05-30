from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm as DjangoUserChangeForm
from django.contrib.auth.models import User
from .models import Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio', 'profile_picture']
        widgets = {
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'profile_picture': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    # Add is_staff and is_active fields for admin creation
    is_staff = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    is_active = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))


    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email', 'first_name', 'last_name', 'is_staff', 'is_active')
        # Ensure default Django UserCreationForm fields also get basic styling if needed
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            # Password fields are already handled well by UserCreationForm's default widgets
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_staff = self.cleaned_data.get('is_staff', False) # Get value or default
        user.is_active = self.cleaned_data.get('is_active', True) # Get value or default
        if commit:
            user.save()
            # Profile creation is handled by signals in models.py, so no need to explicitly create Profile here
        return user


class CustomUserChangeForm(DjangoUserChangeForm):
    # We don't include password here as DjangoUserChangeForm handles it separately.
    # For password changes, Django's built-in views or a separate form is better.
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    is_staff = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    is_active = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    
    class Meta(DjangoUserChangeForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}), # Username might be non-editable
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The password field is complex in UserChangeForm, often better handled by specific views
        # or by removing it if not intended for direct change here.
        # For simplicity in this admin-like interface, we might allow staff status changes, etc.
        # If 'password' field exists in self.fields (it does by default from UserChangeForm), remove it or handle carefully.
        if 'password' in self.fields:
            del self.fields['password'] # Or use UserAdmin.get_form for more control like Django admin does.

    # save method is inherited and should work for User fields.
    # ProfileForm will be handled separately in the view.
