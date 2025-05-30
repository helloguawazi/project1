from django.db import models
from django.core.cache import cache
from django.core.exceptions import ValidationError

class Setting(models.Model):
    SETTING_TYPE_CHOICES = [
        ('string', 'String'),
        ('number', 'Number'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
        ('text', 'Text Area'),
    ]
    
    key = models.CharField(max_length=100, unique=True, help_text="Unique key for the setting, e.g., 'SITE_TITLE', 'SIDEBAR_LAYOUT'.")
    value = models.TextField(help_text="Value of the setting. Store as string, parse based on 'value_type'. For JSON, store valid JSON.")
    value_type = models.CharField(max_length=10, choices=SETTING_TYPE_CHOICES, default='string', help_text="The data type of the setting's value.")
    
    group = models.CharField(max_length=50, default='general', blank=True, help_text="Group for organizing settings, e.g., 'general', 'seo', 'theme'.")
    description = models.TextField(blank=True, help_text="Description of what this setting is for.")
    is_public = models.BooleanField(default=False, help_text="If true, this setting can be exposed via a public API endpoint.")
    is_editable = models.BooleanField(default=True, help_text="If false, this setting can only be changed via code/migrations, not via API/admin.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['group', 'key']

    def __str__(self):
        return f"{self.group}.{self.key}"

    def clean(self):
        """Validate data before saving."""
        super().clean()
        # Validate JSON if type is JSON
        if self.value_type == 'json':
            import json
            try:
                json.loads(self.value)
            except json.JSONDecodeError:
                raise ValidationError({'value': 'Invalid JSON format for this setting value.'})
        # Validate Number if type is Number
        if self.value_type == 'number':
            try:
                float(self.value) # Try to cast to float, allows integers and decimals
            except ValueError:
                raise ValidationError({'value': 'Invalid number format for this setting value.'})
        # Validate Boolean if type is Boolean
        if self.value_type == 'boolean':
            if self.value.lower() not in ['true', 'false', '1', '0']:
                raise ValidationError({'value': "Invalid boolean format. Use 'true', 'false', '1', or '0'."})

    def save(self, *args, **kwargs):
        if not self.is_editable and self.pk: # If trying to save an existing non-editable setting
            # Check if any fields other than 'value' or 'value_type' are being changed by admin/API
            # This logic might be too simple if other fields can be legitimately updated by system processes
            # For now, we prevent changes to 'value' and 'value_type' for non-editable settings via save.
            # A more robust way would be to handle this in forms/serializers for user-facing interfaces.
            db_instance = Setting.objects.get(pk=self.pk)
            if db_instance.value != self.value or db_instance.value_type != self.value_type :
                 # Allowing description, group, is_public to be changed even if not "editable" for its value
                 pass # Not raising ValidationError here, as this might be too restrictive.
                      # Permissions should handle who can edit what. `is_editable` is more a flag for UI.


        self.full_clean() # Call clean() during save
        super().save(*args, **kwargs)
        # Cache invalidation/update
        cache.set(f"setting_{self.key}", self.get_value(), timeout=None) # Cache indefinitely until changed

    def delete(self, *args, **kwargs):
        cache.delete(f"setting_{self.key}")
        super().delete(*args, **kwargs)

    def get_value(self):
        """Returns the value cast to its Python type."""
        if self.value_type == 'string':
            return str(self.value)
        elif self.value_type == 'number':
            try:
                # Attempt to cast to int if it's a whole number, else float
                if '.' in self.value or 'e' in self.value.lower(): # Check for float/scientific notation
                    return float(self.value)
                return int(self.value)
            except ValueError:
                return self.value # Should not happen if clean() was called
        elif self.value_type == 'boolean':
            return self.value.lower() in ['true', '1']
        elif self.value_type == 'json':
            import json
            try:
                return json.loads(self.value)
            except json.JSONDecodeError:
                return None # Should not happen if clean() was called
        elif self.value_type == 'text':
            return str(self.value)
        return self.value

    @classmethod
    def get_setting(cls, key, default=None):
        """Convenience method to get a setting's typed value from cache or DB."""
        cached_value = cache.get(f"setting_{key}")
        if cached_value is not None:
            return cached_value
        
        try:
            setting = cls.objects.get(key=key)
            typed_value = setting.get_value()
            cache.set(f"setting_{setting.key}", typed_value, timeout=None)
            return typed_value
        except cls.DoesNotExist:
            return default

    @classmethod
    def get_public_settings(cls):
        """Returns a dictionary of all public settings and their typed values."""
        public_settings = cls.objects.filter(is_public=True)
        settings_dict = {}
        for setting in public_settings:
            # Try to get from cache first
            cached_value = cache.get(f"setting_{setting.key}")
            if cached_value is not None:
                settings_dict[setting.key] = cached_value
            else:
                typed_value = setting.get_value()
                settings_dict[setting.key] = typed_value
                cache.set(f"setting_{setting.key}", typed_value, timeout=None) # Cache it
        return settings_dict

    @classmethod
    def clear_all_settings_cache(cls, specific_keys=None):
        """
        Clears cached settings.
        If specific_keys (a list of keys) is provided, only those are cleared.
        Otherwise, all settings known to the DB are cleared from cache.
        """
        if specific_keys:
            keys_to_clear = specific_keys
        else:
            keys_to_clear = cls.objects.all().values_list('key', flat=True)
        
        deleted_count = 0
        for key in keys_to_clear:
            if cache.has_key(f"setting_{key}"):
                cache.delete(f"setting_{key}")
                deleted_count +=1
        
        print(f"Cleared cache for {deleted_count} keys: {list(keys_to_clear)}") # For logging/debug
        return deleted_count
