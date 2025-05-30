from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test # For permission checks
from django.contrib.admin.views.decorators import staff_member_required # Specific decorator for staff
from django.contrib.auth.models import User
from django.contrib import messages # For success/error messages
from django.db import transaction # To ensure atomic operations for user and profile

from .models import Profile
from .forms import CustomUserCreationForm, CustomUserChangeForm, ProfileForm

# API Views (already created in previous subtask - keep them)
from rest_framework import generics, permissions, status # Ensure status is imported
from rest_framework.response import Response
from .serializers import UserSerializer, RegisterSerializer, ChangePasswordSerializer, ProfileSerializer

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

class UserProfileView(generics.RetrieveUpdateAPIView): # For API to get/update own User+Profile
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user

class ProfileDetailView(generics.RetrieveUpdateAPIView): # For API to get/update own Profile directly
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user.profile

class ChangePasswordView(generics.UpdateAPIView): # For API
    serializer_class = ChangePasswordSerializer
    model = User
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self, queryset=None):
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            if not self.object.check_password(serializer.data.get("old_password")):
                return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()
            return Response({"detail": "Password updated successfully"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Django Template Views for User Management (AdminLTE)

def is_staff_user(user):
    return user.is_authenticated and user.is_staff

# @login_required
# @user_passes_test(is_staff_user) # Example of a more specific permission
@staff_member_required # Simpler decorator for staff members, handles login redirect too
def user_list_view(request):
    users = User.objects.all().select_related('profile').order_by('username')
    context = {
        'users': users, # Renamed from 'users' to 'user_list_qs' to avoid conflict if ever needed
        'page_title': 'User List',
        'breadcrumb_active': 'Users'
    }
    return render(request, 'accounts/user_list.html', context)

@staff_member_required
def user_create_view(request):
    if request.method == 'POST':
        user_form = CustomUserCreationForm(request.POST)
        # Profile form is not strictly needed at creation if signals handle it,
        # but can be used if you want to set profile fields immediately.
        # For simplicity, we'll rely on signals for Profile creation.
        if user_form.is_valid():
            user = user_form.save()
            messages.success(request, f"User '{user.username}' created successfully.")
            return redirect('accounts_ui:user_list') # Use the correct namespace
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        user_form = CustomUserCreationForm()
    
    context = {
        'user_form': user_form,
        # 'profile_form': ProfileForm(), # If you want to add profile fields at creation
        'form_type': 'create',
        'page_title': 'Create User',
        'breadcrumb_active': 'Create User'
    }
    return render(request, 'accounts/user_form.html', context)

@staff_member_required
def user_edit_view(request, user_id):
    user_to_edit = get_object_or_404(User, id=user_id)
    profile_to_edit = get_object_or_404(Profile, user=user_to_edit) # Profile.objects.get_or_create(user=user_to_edit)[0] is safer

    if request.method == 'POST':
        user_form = CustomUserChangeForm(request.POST, instance=user_to_edit)
        profile_form = ProfileForm(request.POST, request.FILES or None, instance=profile_to_edit)
        
        if user_form.is_valid() and profile_form.is_valid():
            with transaction.atomic(): # Ensure both forms save or neither does
                user_form.save()
                profile_form.save()
            messages.success(request, f"User '{user_to_edit.username}' updated successfully.")
            return redirect('accounts_ui:user_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        user_form = CustomUserChangeForm(instance=user_to_edit)
        profile_form = ProfileForm(instance=profile_to_edit)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'user_instance': user_to_edit, 
        'form_type': 'edit',
        'page_title': f'Edit User: {user_to_edit.username}',
        'breadcrumb_active': 'Edit User'
    }
    return render(request, 'accounts/user_form.html', context)
